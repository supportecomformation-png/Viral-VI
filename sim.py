"""
CopyLab — pages et API de la démo de copy trading (argent fictif).

Rien ne transite par ce site : aucun dépôt, aucun vrai wallet connecté. Les
performances des wallets sont SIMULÉES à partir de leur adresse (voir
static/js/engine.js). Le serveur ne stocke que les paramètres d'une
simulation ; l'état est recalculé côté client, de façon déterministe.
"""

import json
import re
import time

from flask import Blueprint, render_template, request, jsonify, g, redirect, url_for, flash, abort, current_app

import onchain
from auth_utils import login_required
from db import query_all, query_one, execute

bp = Blueprint("sim", __name__)

EVM_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
SOL_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")

MIN_BALANCE = 1.0
MAX_BALANCE = 1000000.0
ALLOWED_ALLOC = (0.05, 0.1, 0.25, 0.5)
ALLOWED_SPEEDS = (300, 1200, 6000)
ALLOWED_MODES = ("live", "backtest")
ALLOWED_SOURCES = ("simulated", "onchain")
MAX_SIMULATIONS_PER_USER = 30

# Traders "vedettes" de la démo : des adresses fictives dont le track record
# est généré par le moteur de simulation (rien à voir avec de vrais wallets).
DEMO_TRADERS = [
    {"handle": "MoonFarmer", "wallet": "0xdd5782086918b3114daa8818ca48d9a220bb125c", "chain": "evm",
     "bio": "Swing sur les memecoins Base, positions de quelques heures."},
    {"handle": "SolSniper", "wallet": "uEUmJSvfB32wmfBgqoFtucjCZSjXSZkLfVBWKLMV73Ji", "chain": "solana",
     "bio": "Snipe les nouveaux lancements Solana, sorties rapides."},
    {"handle": "AlphaWhale", "wallet": "0xa29cfd8a87dfbd0222ae1208e8e8ccdc28a80dd7", "chain": "evm",
     "bio": "Grosses convictions, peu de trades, gros multiples."},
    {"handle": "StackQueen", "wallet": "q8w6HauUZ2PSnX5icu1zbJUdbHM5dBWUFWV3PgLrDxR", "chain": "solana",
     "bio": "Entrées échelonnées, gestion du risque stricte."},
    {"handle": "ChadTrades", "wallet": "8XppUi3uK7ZiJzzD6dq415g9WEUgXRZwuP9VVa643Tu", "chain": "solana",
     "bio": "Suit la narration du moment, sort avant la foule."},
    {"handle": "OrbitOG", "wallet": "0x81b853259b394fa58a1385d342419a585a6f6d0c", "chain": "evm",
     "bio": "Trader historique, rotation rapide entre les tokens."},
    {"handle": "DegenMarie", "wallet": "xcJ8pA1VY5YqEL9GcTp37uVo5xDTLN2pgm1UiNNMDzs", "chain": "solana",
     "bio": "Profil agressif : gros gains, quelques gros ratés."},
    {"handle": "ColdHands", "wallet": "0x7350a8028a44a1fce27466c73c73da71167887b2", "chain": "evm",
     "bio": "Prend ses profits tôt et ne regarde plus le graphique."},
    {"handle": "BaseBaron", "wallet": "0x26f17167832f55894eb63f2b883b431475f4ba33", "chain": "evm",
     "bio": "Spécialiste de l'écosystème Base."},
    {"handle": "FlashFrank", "wallet": "94rqYW6pq1wfaT7ds2JrJQw63U7cm2zV6gNvnmhE5qvr", "chain": "solana",
     "bio": "Scalping : des dizaines de petits trades par semaine."},
    {"handle": "YukiSwing", "wallet": "0x154d5160d21801936513c8b8a3348cde0baa37da", "chain": "evm",
     "bio": "Swing trading patient, quelques positions à la fois."},
    {"handle": "PaperNinja", "wallet": "hnNrRy9AqHV8yhtbdgj6ShArwY4Hgp2vovUhsdVRADzh", "chain": "solana",
     "bio": "Régulier et discret : peu de bruit, perf stable."},
]
TRADERS_BY_WALLET = {t["wallet"]: t for t in DEMO_TRADERS}


def detect_chain(address):
    address = (address or "").strip()
    if EVM_RE.match(address):
        return "evm"
    if SOL_RE.match(address):
        return "solana"
    return None


def normalize_wallet(address, chain):
    address = address.strip()
    return address.lower() if chain == "evm" else address


def _error(code, message, status):
    return jsonify({"error": code, "message": message}), status


def _onchain_enabled():
    return bool(current_app.config.get("MORALIS_API_KEY"))


def _payload_for(wallet, chain, network, max_age):
    """Trades on-chain d'un wallet : cache si assez récent, sinon appel au fournisseur."""
    payload = onchain.cached_payload(wallet, network, max_age)
    if payload is not None:
        return payload
    if onchain.fetches_last_24h() >= current_app.config["ONCHAIN_MAX_FETCHES_PER_DAY"]:
        raise onchain.ProviderError(
            "budget", "Le quota quotidien d'analyses de wallets est atteint. Réessaie demain.", 429
        )
    payload = onchain.get_wallet_trades(wallet, chain, network, current_app.config["MORALIS_API_KEY"])
    onchain.store_payload(wallet, network, payload)
    return payload


def _serialize(row):
    trader = TRADERS_BY_WALLET.get(row["wallet"])
    source = row.get("source") or "simulated"
    snapshot = None
    if source == "onchain" and row.get("snapshot"):
        try:
            snapshot = json.loads(row["snapshot"])
        except ValueError:
            snapshot = None
    return {
        "id": row["id"],
        "wallet": row["wallet"],
        "chain": row["chain"],
        "mode": row["mode"],
        "balance": float(row["balance"]),
        "alloc_pct": float(row["alloc_pct"]),
        "speed": int(row["speed"]),
        "started_at": float(row["started_at"]),
        "stopped_at": float(row["stopped_at"]) if row["stopped_at"] is not None else None,
        "handle": trader["handle"] if trader else None,
        "source": source,
        "network": row.get("network"),
        "snapshot": snapshot,
    }


def _owned_simulation(sim_id):
    return query_one(
        "SELECT * FROM simulations WHERE id = ? AND user_id = ?", (sim_id, g.user["id"])
    )


# ---------------------------------------------------------------- pages

@bp.route("/traders")
def traders():
    return render_template("traders.html", traders=DEMO_TRADERS, onchain_enabled=_onchain_enabled())


@bp.route("/trader/<path:wallet>")
def trader(wallet):
    chain = detect_chain(wallet)
    if chain is None:
        flash("Adresse de wallet invalide. Colle une adresse Solana ou EVM (0x…).", "error")
        return redirect(url_for("sim.traders"))
    wallet = normalize_wallet(wallet, chain)
    return render_template(
        "trader.html",
        wallet=wallet,
        chain=chain,
        featured=TRADERS_BY_WALLET.get(wallet),
        onchain=_onchain_enabled() and wallet not in TRADERS_BY_WALLET,
        networks=onchain.EVM_NETWORKS,
        default_network=onchain.network_for(chain, request.args.get("network")),
    )


@bp.route("/app")
@login_required
def my_simulations():
    return render_template("app.html")


@bp.route("/sim/<int:sim_id>")
@login_required
def simulation_page(sim_id):
    row = _owned_simulation(sim_id)
    if row is None:
        abort(404)
    # Données embarquées : la page n'a pas besoin d'un aller-retour API supplémentaire.
    return render_template("sim.html", sim_id=sim_id,
                           sim_boot={"simulation": _serialize(row), "server_now": time.time()})


# ------------------------------------------------------------------ API

@bp.route("/api/wallet/<path:wallet>/trades")
def wallet_trades(wallet):
    """Trades on-chain réels d'un wallet (30 jours), ou `source: simulated` si indisponible."""
    chain = detect_chain(wallet)
    if chain is None:
        return _error("invalid_wallet", "Adresse de wallet invalide (Solana ou EVM 0x…).", 400)
    wallet = normalize_wallet(wallet, chain)
    if wallet in TRADERS_BY_WALLET:
        return jsonify(source="simulated", reason="featured")
    if not _onchain_enabled():
        return jsonify(source="simulated", reason="no_api_key")
    network = onchain.network_for(chain, request.args.get("network"))
    try:
        data = _payload_for(wallet, chain, network, current_app.config["ONCHAIN_CACHE_TTL_SECONDS"])
    except onchain.ProviderError as exc:
        return _error(exc.code, exc.message, exc.status)
    return jsonify(data)


@bp.route("/api/wallets/leaderboard")
def wallets_leaderboard():
    """Wallets réels récemment analysés, classés par rendement réalisé sur 30 jours."""
    if not _onchain_enabled():
        return jsonify(wallets=[])
    rows = []
    for wallet, network, data in onchain.recent_payloads():
        stats = data.get("stats") or {}
        if data.get("source") != "onchain" or (stats.get("trades") or 0) < 5 or stats.get("roi") is None:
            continue
        rows.append({
            "wallet": wallet,
            "network": network,
            "chain": data.get("chain"),
            "roi": stats["roi"],
            "win_rate": stats.get("win_rate"),
            "trades": stats["trades"],
            "pnl_usd": stats.get("pnl_usd"),
            "curve": stats.get("curve") or [],
            "fetched_at": data.get("fetched_at"),
        })
    rows.sort(key=lambda r: -r["roi"])
    return jsonify(wallets=rows[:20])


@bp.route("/api/simulations", methods=["GET"])
@login_required
def list_simulations():
    rows = query_all(
        "SELECT * FROM simulations WHERE user_id = ? ORDER BY id DESC", (g.user["id"],)
    )
    return jsonify(simulations=[_serialize(r) for r in rows], server_now=time.time())


@bp.route("/api/simulations", methods=["POST"])
@login_required
def create_simulation():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    wallet = str(payload.get("wallet", "")).strip()
    chain = detect_chain(wallet)
    if chain is None:
        return _error("invalid_wallet", "Adresse de wallet invalide (Solana ou EVM 0x…).", 400)
    wallet = normalize_wallet(wallet, chain)

    try:
        balance = float(payload.get("balance", 10000))
        alloc_pct = float(payload.get("alloc_pct", 0.1))
        speed = int(payload.get("speed", 1200))
    except (TypeError, ValueError):
        return _error("invalid_params", "Paramètres de simulation invalides.", 400)
    mode = payload.get("mode", "live")
    balance = round(balance, 2)

    if (
        not (MIN_BALANCE <= balance <= MAX_BALANCE)
        or not any(abs(alloc_pct - a) < 1e-9 for a in ALLOWED_ALLOC)
        or speed not in ALLOWED_SPEEDS
        or mode not in ALLOWED_MODES
    ):
        return _error("invalid_params", "Paramètres de simulation invalides.", 400)

    count = query_one(
        "SELECT COUNT(*) AS c FROM simulations WHERE user_id = ?", (g.user["id"],)
    )["c"]
    if count >= MAX_SIMULATIONS_PER_USER:
        return _error(
            "too_many",
            "Limite atteinte (%d simulations). Supprime-en une pour en lancer une nouvelle."
            % MAX_SIMULATIONS_PER_USER,
            409,
        )

    source = payload.get("source", "simulated")
    if source not in ALLOWED_SOURCES:
        return _error("invalid_params", "Paramètres de simulation invalides.", 400)

    network = None
    snapshot = None
    if source == "onchain":
        if wallet in TRADERS_BY_WALLET or not _onchain_enabled():
            return _error("onchain_unavailable", "Les données on-chain ne sont pas disponibles pour ce wallet.", 400)
        network = onchain.network_for(chain, payload.get("network"))
        try:
            data = _payload_for(wallet, chain, network, current_app.config["ONCHAIN_CACHE_TTL_SECONDS"])
        except onchain.ProviderError as exc:
            return _error(exc.code, exc.message, exc.status)
        if not data.get("trades"):
            return _error(
                "no_trades",
                "Aucun trade clôturé sur les 30 derniers jours pour ce wallet : rien à copier.",
                400,
            )
        # Instantané des trades : la simulation reste identique même si le cache change.
        snapshot = json.dumps(data, separators=(",", ":"))

    sim_id = execute(
        """INSERT INTO simulations
           (user_id, wallet, chain, mode, balance, alloc_pct, speed, started_at, source, network, snapshot)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (g.user["id"], wallet, chain, mode, balance, alloc_pct, speed, time.time(), source, network, snapshot),
    )
    row = _owned_simulation(sim_id)
    return jsonify(simulation=_serialize(row), server_now=time.time()), 201


@bp.route("/api/simulations/<int:sim_id>", methods=["GET"])
@login_required
def get_simulation(sim_id):
    row = _owned_simulation(sim_id)
    if row is None:
        return _error("not_found", "Simulation introuvable.", 404)
    return jsonify(simulation=_serialize(row), server_now=time.time())


@bp.route("/api/simulations/<int:sim_id>/stop", methods=["POST"])
@login_required
def stop_simulation(sim_id):
    if _owned_simulation(sim_id) is None:
        return _error("not_found", "Simulation introuvable.", 404)
    execute(
        """UPDATE simulations SET stopped_at = ?
           WHERE id = ? AND user_id = ? AND mode = 'live' AND stopped_at IS NULL""",
        (time.time(), sim_id, g.user["id"]),
    )
    # Simulation arrêtée : on annule les notifications qui n'étaient pas encore parties.
    execute("DELETE FROM push_queue WHERE sim_id = ? AND sent_at IS NULL", (sim_id,))
    return jsonify(simulation=_serialize(_owned_simulation(sim_id)), server_now=time.time())


@bp.route("/api/simulations/<int:sim_id>", methods=["DELETE"])
@login_required
def delete_simulation(sim_id):
    deleted = execute(
        "DELETE FROM simulations WHERE id = ? AND user_id = ?", (sim_id, g.user["id"])
    )
    if not deleted:
        return _error("not_found", "Simulation introuvable.", 404)
    return jsonify(ok=True)
