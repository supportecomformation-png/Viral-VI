"""
Données on-chain réelles pour CopyLab (lecture seule, via l'API Moralis).

Pour un wallet Solana ou EVM, on récupère ses swaps DEX des 30 derniers jours
(avec la valeur en dollars de chaque swap) puis on reconstitue des « trades » :
un trade = un cycle achat(s) -> vente(s) sur un même token, de la première
entrée à la sortie complète. Le rendement est réalisé : valeur vendue / coût
d'achat - 1 (en dollars, au moment des swaps).

Limites assumées (affichées dans l'interface) :
- seuls les trades CLÔTURÉS dans la fenêtre sont retenus (les positions encore
  ouvertes sont listées à part, sans valorisation) ;
- une vente sans achat connu dans la fenêtre est ignorée (pas de prix de revient) ;
- les swaps entre deux « monnaies de référence » (SOL->USDC…) sont ignorés ;
- la courbe intermédiaire d'un trade est interpolée (seuls l'entrée et la sortie
  sont réelles).
"""

import json
import re
import time
from datetime import datetime, timezone

import requests

from db import query_all, query_one, execute

MORALIS_EVM_URL = "https://deep-index.moralis.io/api/v2.2/wallets/{address}/swaps"
MORALIS_SOL_URL = "https://solana-gateway.moralis.io/account/mainnet/{address}/swaps"

EVM_NETWORKS = {
    "base": "Base",
    "eth": "Ethereum",
    "bsc": "BNB Chain",
    "arbitrum": "Arbitrum",
    "polygon": "Polygon",
    "optimism": "Optimism",
}
DEFAULT_EVM_NETWORK = "base"

WINDOW_DAYS = 30
PAGE_LIMIT = 100
MAX_PAGES = 4
TIME_BUDGET_SECONDS = 7.0
REQUEST_TIMEOUT_SECONDS = 6
MIN_CYCLE_USD = 5.0
MAX_RET = 50.0  # +5000 % : au-delà on suspecte une donnée aberrante

# Monnaies de référence : une jambe de swap sur l'un de ces symboles n'est pas
# un « trade » mais le moyen de payer / d'encaisser.
QUOTE_SYMBOLS = {
    "SOL", "WSOL", "USDC", "USDT", "USDC.E", "USDS", "DAI", "PYUSD", "USDE", "FDUSD",
    "ETH", "WETH", "BNB", "WBNB", "POL", "MATIC", "WMATIC", "AVAX", "WAVAX",
}


class ProviderError(Exception):
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def network_for(chain, requested):
    if chain == "solana":
        return "solana"
    return requested if requested in EVM_NETWORKS else DEFAULT_EVM_NETWORK


# ------------------------------------------------------------------ fournisseur

def _get(url, params, api_key):
    try:
        resp = requests.get(
            url,
            params=params,
            headers={"X-API-Key": api_key, "accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise ProviderError("provider_unreachable", "Fournisseur on-chain injoignable, réessaie dans un instant.", 502)
    if resp.status_code == 429:
        raise ProviderError("rate_limited", "Limite du fournisseur on-chain atteinte, réessaie dans un instant.", 429)
    if resp.status_code in (401, 403):
        raise ProviderError("provider_auth", "Clé API on-chain refusée par le fournisseur.", 502)
    if resp.status_code >= 400:
        raise ProviderError("provider_error", "Erreur du fournisseur on-chain (%d)." % resp.status_code, 502)
    try:
        return resp.json()
    except ValueError:
        raise ProviderError("provider_error", "Réponse invalide du fournisseur on-chain.", 502)


def fetch_swaps(wallet, chain, network, api_key, since_ts):
    """Renvoie (liste de swaps bruts, tronqué?)."""
    if chain == "solana":
        url = MORALIS_SOL_URL.format(address=wallet)
        params = {"order": "DESC", "limit": PAGE_LIMIT, "fromDate": str(int(since_ts))}
    else:
        url = MORALIS_EVM_URL.format(address=wallet)
        iso = datetime.fromtimestamp(since_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        params = {"chain": network, "order": "DESC", "limit": PAGE_LIMIT, "fromDate": iso}

    swaps = []
    cursor = None
    truncated = False
    started = time.monotonic()
    for _ in range(MAX_PAGES):
        page_params = dict(params)
        if cursor:
            page_params["cursor"] = cursor
        data = _get(url, page_params, api_key)
        items = data.get("result") if isinstance(data, dict) else None
        items = items or []
        swaps.extend(items)
        cursor = data.get("cursor") if isinstance(data, dict) else None
        if not cursor or len(items) < PAGE_LIMIT:
            break
        if time.monotonic() - started > TIME_BUDGET_SECONDS:
            truncated = True
            break
    else:
        truncated = bool(cursor)
    return swaps, truncated


# --------------------------------------------------------------- normalisation

def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return v if v == v and v not in (float("inf"), float("-inf")) else 0.0


def _timestamp(value):
    """ISO 8601 ('2026-09-25T10:32:11.000Z') ou epoch (secondes / millisecondes)."""
    if value is None:
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        ts = float(value)
        return ts / 1000.0 if ts > 1e11 else ts
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _clean_symbol(symbol):
    cleaned = re.sub(r"[^A-Za-z0-9]", "", symbol or "")[:12].upper()
    return cleaned or "TOKEN"


def swap_legs(item):
    """Décompose un swap en jambes (temps, clé de token, symbole, 'buy'|'sell', usd, quantité)."""
    ts = _timestamp(item.get("blockTimestamp"))
    if ts is None:
        return []
    bought = item.get("bought") or {}
    sold = item.get("sold") or {}
    total = _num(item.get("totalValueUsd"))
    legs = []

    def leg(side_obj, kind):
        symbol_raw = (side_obj.get("symbol") or "").strip()
        if not symbol_raw and not side_obj.get("address"):
            return
        if symbol_raw.upper() in QUOTE_SYMBOLS:
            return
        usd = _num(side_obj.get("usdAmount")) or total
        qty = _num(side_obj.get("amount"))
        if usd <= 0 or qty <= 0:
            return
        key = (side_obj.get("address") or symbol_raw).lower()
        legs.append((ts, key, _clean_symbol(symbol_raw), kind, usd, qty))

    leg(bought, "buy")
    leg(sold, "sell")
    return legs


def build_trades(swaps):
    """Swaps bruts -> (trades clôturés, positions encore ouvertes)."""
    legs = []
    for item in swaps:
        legs.extend(swap_legs(item))
    legs.sort(key=lambda l: (l[0], 0 if l[3] == "buy" else 1))

    positions = {}
    trades = []
    used_ids = set()

    for ts, key, symbol, kind, usd, qty in legs:
        pos = positions.get(key)
        if kind == "buy":
            if pos is None:
                pos = positions[key] = {
                    "symbol": symbol, "qty": 0.0, "peak": 0.0, "cost": 0.0, "proceeds": 0.0, "open": ts,
                }
            pos["qty"] += qty
            pos["peak"] = max(pos["peak"], pos["qty"])
            pos["cost"] += usd
            continue

        if pos is None or pos["qty"] <= 0:
            continue  # vente sans prix de revient connu dans la fenêtre
        sold_qty = min(qty, pos["qty"])
        pos["proceeds"] += usd * (sold_qty / qty)
        pos["qty"] -= sold_qty
        if pos["qty"] <= max(1e-12, pos["peak"] * 0.02):
            del positions[key]
            if pos["cost"] < MIN_CYCLE_USD:
                continue
            ret = max(-0.999, min(MAX_RET, pos["proceeds"] / pos["cost"] - 1.0))
            open_ts = int(pos["open"])
            close_ts = max(int(ts), open_ts + 60)
            trade_id = "%s-%d" % (key[:8], open_ts)
            n = 1
            while trade_id in used_ids:
                n += 1
                trade_id = "%s-%d-%d" % (key[:8], open_ts, n)
            used_ids.add(trade_id)
            trades.append({
                "id": trade_id,
                "token": pos["symbol"],
                "open": open_ts,
                "close": close_ts,
                "ret": round(ret, 6),
                "size_usd": round(pos["cost"], 2),
            })

    trades.sort(key=lambda t: t["open"])
    open_positions = [
        {"token": p["symbol"], "open": int(p["open"]), "cost_usd": round(p["cost"], 2)}
        for p in positions.values()
        if p["qty"] > 0 and p["cost"] >= MIN_CYCLE_USD
    ]
    open_positions.sort(key=lambda p: -p["open"])
    return trades, open_positions


def summarize(trades):
    """Statistiques réalisées + courbe de PnL cumulé (en $) par date de clôture."""
    if not trades:
        return {"trades": 0, "win_rate": None, "roi": None, "pnl_usd": 0.0, "volume_usd": 0.0, "curve": []}
    volume = sum(t["size_usd"] for t in trades)
    pnl = sum(t["size_usd"] * t["ret"] for t in trades)
    wins = sum(1 for t in trades if t["ret"] > 0)
    running = 0.0
    curve = [0.0]
    for t in sorted(trades, key=lambda t: t["close"]):
        running += t["size_usd"] * t["ret"]
        curve.append(round(running, 2))
    if len(curve) > 40:
        step = (len(curve) - 1) / 39.0
        curve = [curve[int(round(i * step))] for i in range(40)]
    return {
        "trades": len(trades),
        "win_rate": round(wins / len(trades), 4),
        "roi": round(pnl / volume, 6) if volume else None,
        "pnl_usd": round(pnl, 2),
        "volume_usd": round(volume, 2),
        "curve": curve,
    }


def get_wallet_trades(wallet, chain, network, api_key, now=None):
    """Interroge le fournisseur et renvoie la charge utile prête à être mise en cache."""
    now = time.time() if now is None else now
    window_start = now - WINDOW_DAYS * 86400
    swaps, truncated = fetch_swaps(wallet, chain, network, api_key, window_start)
    trades, open_positions = build_trades(swaps)
    trades = [t for t in trades if t["open"] >= window_start]
    return {
        "source": "onchain",
        "provider": "moralis",
        "chain": chain,
        "network": network,
        "window_start": int(window_start),
        "window_end": int(now),
        "fetched_at": int(now),
        "swaps_count": len(swaps),
        "truncated": truncated,
        "trades": trades,
        "open_positions": open_positions[:20],
        "stats": summarize(trades),
    }


# ------------------------------------------------------------------------ cache

def cached_payload(wallet, network, max_age, now=None):
    now = time.time() if now is None else now
    row = query_one(
        "SELECT payload, fetched_at FROM wallet_cache WHERE wallet = ? AND network = ?",
        (wallet, network),
    )
    if row and now - float(row["fetched_at"]) <= max_age:
        try:
            return json.loads(row["payload"])
        except ValueError:
            return None
    return None


def store_payload(wallet, network, payload):
    execute(
        """INSERT INTO wallet_cache (wallet, network, payload, fetched_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT (wallet, network) DO UPDATE SET
             payload = EXCLUDED.payload, fetched_at = EXCLUDED.fetched_at""",
        (wallet, network, json.dumps(payload, separators=(",", ":")), float(payload["fetched_at"])),
    )


def fetches_last_24h(now=None):
    now = time.time() if now is None else now
    row = query_one("SELECT COUNT(*) AS c FROM wallet_cache WHERE fetched_at > ?", (now - 86400,))
    return int(row["c"]) if row else 0


def recent_payloads(limit=60, max_age=7 * 86400, now=None):
    """Derniers wallets analysés : liste de (wallet, réseau, charge utile)."""
    now = time.time() if now is None else now
    rows = query_all(
        "SELECT wallet, network, payload FROM wallet_cache WHERE fetched_at > ? ORDER BY fetched_at DESC LIMIT ?",
        (now - max_age, int(limit)),
    )
    out = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except ValueError:
            continue
        out.append((row["wallet"], row["network"], payload))
    return out
