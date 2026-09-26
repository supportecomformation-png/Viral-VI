"""
Prix des cryptomonnaies pour la page d'accueil (lecture seule).

Source principale : CoinGecko (API publique, sans clé). Secours : CoinPaprika.
Le serveur met la liste en cache 60 s dans `market_cache` (partagé entre
toutes les instances serverless) pour rester loin des limites de débit. Si les
deux fournisseurs échouent, on sert le dernier cache disponible (marqué
`stale`) ; s'il n'y en a aucun, l'erreur remonte : on n'invente jamais de prix.
"""

import json
import time

import requests
from flask import Blueprint, jsonify

from db import query_one, execute

bp = Blueprint("markets", __name__)

COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
PAPRIKA_URL = "https://api.coinpaprika.com/v1/tickers"
PAPRIKA_LOGO = "https://static.coinpaprika.com/coin/{id}/logo.png"

TOP_N = 250
FRESH_SECONDS = 60
STALE_MAX_SECONDS = 24 * 3600
COINGECKO_TIMEOUT = 4.5
PAPRIKA_TIMEOUT = 5.0
CACHE_KEY = "markets:usd"


class MarketError(Exception):
    pass


def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def normalize_coingecko(items):
    coins = []
    for it in items or []:
        price = _num(it.get("current_price"))
        if price is None or not it.get("id"):
            continue
        coins.append({
            "id": it["id"],
            "symbol": str(it.get("symbol") or "").upper(),
            "name": it.get("name") or "",
            "image": it.get("image") or "",
            "price": price,
            "market_cap": _num(it.get("market_cap")),
            "volume": _num(it.get("total_volume")),
            "change_24h": _num(it.get("price_change_percentage_24h")),
            "rank": it.get("market_cap_rank"),
        })
    return coins


def normalize_paprika(items):
    coins = []
    for it in items or []:
        usd = (it.get("quotes") or {}).get("USD") or {}
        price = _num(usd.get("price"))
        if price is None or not it.get("id"):
            continue
        coins.append({
            "id": it["id"],
            "symbol": str(it.get("symbol") or "").upper(),
            "name": it.get("name") or "",
            "image": PAPRIKA_LOGO.format(id=it["id"]),
            "price": price,
            "market_cap": _num(usd.get("market_cap")),
            "volume": _num(usd.get("volume_24h")),
            "change_24h": _num(usd.get("percent_change_24h")),
            "rank": it.get("rank"),
        })
    coins.sort(key=lambda c: (c["rank"] is None or c["rank"] == 0, c["rank"] or 0))
    return coins


def _fetch_json(url, params, timeout):
    try:
        resp = requests.get(url, params=params, timeout=timeout, headers={"accept": "application/json"})
    except requests.RequestException as exc:
        raise MarketError("réseau : %s" % exc)
    if resp.status_code != 200:
        raise MarketError("HTTP %s" % resp.status_code)
    try:
        return resp.json()
    except ValueError:
        raise MarketError("JSON invalide")


def fetch_markets():
    """Interroge CoinGecko puis CoinPaprika. Renvoie (source, liste de coins)."""
    errors = []
    try:
        data = _fetch_json(COINGECKO_URL, {
            "vs_currency": "usd", "order": "market_cap_desc", "per_page": TOP_N,
            "page": 1, "price_change_percentage": "24h",
        }, COINGECKO_TIMEOUT)
        coins = normalize_coingecko(data if isinstance(data, list) else [])
        if coins:
            return "coingecko", coins
        errors.append("coingecko : réponse vide")
    except MarketError as exc:
        errors.append("coingecko : %s" % exc)
    try:
        data = _fetch_json(PAPRIKA_URL, {"quotes": "USD"}, PAPRIKA_TIMEOUT)
        coins = normalize_paprika(data if isinstance(data, list) else [])[:TOP_N]
        if coins:
            return "coinpaprika", coins
        errors.append("coinpaprika : réponse vide")
    except MarketError as exc:
        errors.append("coinpaprika : %s" % exc)
    raise MarketError(" ; ".join(errors))


def _cached(now):
    row = query_one("SELECT payload, fetched_at FROM market_cache WHERE key = ?", (CACHE_KEY,))
    if not row:
        return None, None
    try:
        return json.loads(row["payload"]), float(row["fetched_at"])
    except (ValueError, TypeError):
        return None, None


def _store(payload):
    execute(
        """INSERT INTO market_cache (key, payload, fetched_at) VALUES (?, ?, ?)
           ON CONFLICT (key) DO UPDATE SET payload = EXCLUDED.payload, fetched_at = EXCLUDED.fetched_at""",
        (CACHE_KEY, json.dumps(payload, separators=(",", ":")), float(payload["fetched_at"])),
    )


def get_markets(now=None):
    now = time.time() if now is None else now
    cached, fetched_at = _cached(now)
    if cached is not None and now - fetched_at <= FRESH_SECONDS:
        cached["stale"] = False
        return cached
    try:
        source, coins = fetch_markets()
    except MarketError:
        if cached is not None and now - fetched_at <= STALE_MAX_SECONDS:
            cached["stale"] = True
            return cached
        raise
    payload = {"source": source, "fetched_at": int(now), "stale": False, "coins": coins}
    _store(payload)
    return payload


@bp.route("/api/markets")
def markets():
    try:
        payload = get_markets()
    except MarketError:
        return jsonify(
            error="markets_unavailable",
            message="Les prix sont momentanément indisponibles, réessaie dans un instant.",
        ), 502
    resp = jsonify(payload)
    resp.headers["Cache-Control"] = "public, max-age=15"
    return resp
