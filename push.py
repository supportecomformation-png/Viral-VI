"""
Copy Trade — notifications push (Web Push + VAPID).

Chaque trade copié (achat / vente) peut déclencher une notification sur
l'écran de verrouillage du téléphone, même quand le site est fermé.

Fonctionnement :
  1. Le navigateur s'abonne (service worker + PushManager) → `/api/push/subscribe`.
  2. Quand une copie est lancée, le client calcule les premiers trades de la
     simulation (moteur JS déterministe) et les dépose dans `push_queue` →
     `/api/simulations/<id>/notifications`, tous à l'heure actuelle : c'est une
     rafale, comme une pile de notifications sur l'écran de verrouillage.
  3. Le client appelle aussitôt `/api/push/dispatch`, qui envoie ce qui est dû.
     Aucun déclencheur externe n'est nécessaire. L'endpoint est idempotent :
     chaque notification est « réservée » avant l'envoi, donc jamais envoyée deux fois.

Sans VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY, la fonctionnalité est désactivée
(l'interface masque simplement le bloc de notifications).
"""

import json
import time

from flask import Blueprint, current_app, g, jsonify, request

from auth_utils import login_required
from db import execute, query_all, query_one

bp = Blueprint("push", __name__)

MAX_EVENTS_PER_REQUEST = 40
MAX_QUEUED_PER_SIM = 60
MAX_SUBSCRIPTIONS_PER_USER = 10
STALE_SECONDS = 300            # une notification en retard de plus de 5 min est abandonnée
DISPATCH_BATCH = 25            # notifications traitées par appel
DISPATCH_BUDGET_SECONDS = 7.0  # reste sous la limite d'exécution d'une fonction serverless
SEND_TIMEOUT = 5


def _error(code, message, status):
    return jsonify({"error": code, "message": message}), status


def _enabled():
    cfg = current_app.config
    return bool(cfg.get("VAPID_PUBLIC_KEY") and cfg.get("VAPID_PRIVATE_KEY"))


def _clip(value, limit):
    return str(value or "").strip()[:limit]


# ------------------------------------------------------------------ envoi

class SubscriptionGone(Exception):
    """Le service push a répondu 404/410 : l'abonnement n'existe plus."""


def _send_one(sub, payload):
    """Envoie `payload` (dict) à un abonnement. Lève SubscriptionGone si expiré."""
    from pywebpush import WebPushException, webpush  # import tardif : lourd + absent des tests

    cfg = current_app.config
    try:
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
            },
            data=json.dumps(payload),
            vapid_private_key=cfg["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": cfg["VAPID_SUBJECT"]},  # copie neuve : pywebpush la modifie
            ttl=3600,
            timeout=SEND_TIMEOUT,
        )
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            raise SubscriptionGone() from exc
        raise


def _deliver(user_id, payload, subs_cache=None):
    """Envoie à tous les appareils d'un utilisateur. Renvoie (envoyés, échecs)."""
    if subs_cache is not None and user_id in subs_cache:
        subs = subs_cache[user_id]
    else:
        subs = query_all("SELECT * FROM push_subscriptions WHERE user_id = ?", (user_id,))
        if subs_cache is not None:
            subs_cache[user_id] = subs
    sent = failed = 0
    for sub in subs:
        try:
            _send_one(sub, payload)
            sent += 1
        except SubscriptionGone:
            execute("DELETE FROM push_subscriptions WHERE id = ?", (sub["id"],))
        except Exception as exc:  # réseau, service push indisponible…
            current_app.logger.warning("push: envoi échoué (%s)", exc)
            failed += 1
    return sent, failed


# ------------------------------------------------------------------ API

@bp.route("/api/push/config")
def push_config():
    enabled = _enabled()
    return jsonify(enabled=enabled, public_key=current_app.config["VAPID_PUBLIC_KEY"] if enabled else None)


@bp.route("/api/push/subscribe", methods=["POST"])
@login_required
def subscribe():
    if not _enabled():
        return _error("push_disabled", "Les notifications ne sont pas activées sur ce serveur.", 503)
    data = request.get_json(silent=True) or {}
    sub = data.get("subscription") or {}
    keys = sub.get("keys") or {}
    endpoint = _clip(sub.get("endpoint"), 1024)
    p256dh = _clip(keys.get("p256dh"), 200)
    auth = _clip(keys.get("auth"), 100)
    if not endpoint.startswith("https://") or not p256dh or not auth:
        return _error("invalid_subscription", "Abonnement invalide.", 400)

    existing = query_one("SELECT id, user_id FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    if existing:
        execute(
            "UPDATE push_subscriptions SET user_id = ?, p256dh = ?, auth = ? WHERE id = ?",
            (g.user["id"], p256dh, auth, existing["id"]),
        )
    else:
        count = query_one("SELECT COUNT(*) AS n FROM push_subscriptions WHERE user_id = ?", (g.user["id"],))
        if count and count["n"] >= MAX_SUBSCRIPTIONS_PER_USER:
            execute(
                """DELETE FROM push_subscriptions WHERE id = (
                       SELECT id FROM push_subscriptions WHERE user_id = ? ORDER BY id LIMIT 1)""",
                (g.user["id"],),
            )
        execute(
            "INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, created_at) VALUES (?, ?, ?, ?, ?)",
            (g.user["id"], endpoint, p256dh, auth, time.time()),
        )
    return jsonify(ok=True)


@bp.route("/api/push/unsubscribe", methods=["POST"])
@login_required
def unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = _clip(data.get("endpoint"), 1024)
    if endpoint:
        execute("DELETE FROM push_subscriptions WHERE endpoint = ? AND user_id = ?", (endpoint, g.user["id"]))
    return jsonify(ok=True)


@bp.route("/api/push/status")
@login_required
def status():
    """Dit si cet utilisateur a au moins un appareil abonné (le client vérifie aussi son endpoint)."""
    row = query_one("SELECT COUNT(*) AS n FROM push_subscriptions WHERE user_id = ?", (g.user["id"],))
    return jsonify(enabled=_enabled(), devices=int(row["n"]) if row else 0)


@bp.route("/api/push/test", methods=["POST"])
@login_required
def test_push():
    if not _enabled():
        return _error("push_disabled", "Les notifications ne sont pas activées sur ce serveur.", 503)
    sent, failed = _deliver(
        g.user["id"],
        {
            "title": "Copy Trade",
            "body": "Les notifications sont activées. Tu seras prévenu à chaque trade copié.",
            "url": "/app",
            "tag": "test-%d" % int(time.time()),
        },
    )
    if not sent:
        return _error("no_device", "Aucun appareil n'a reçu la notification. Réactive-les puis réessaie.", 502)
    return jsonify(sent=sent, failed=failed)


@bp.route("/api/simulations/<int:sim_id>/notifications", methods=["POST"])
@login_required
def schedule_notifications(sim_id):
    """Dépose les notifications à venir d'une simulation (calculées par le client).

    Idempotent : une même clé d'événement n'est enregistrée qu'une fois.
    """
    sim = query_one(
        "SELECT id, mode, stopped_at FROM simulations WHERE id = ? AND user_id = ?",
        (sim_id, g.user["id"]),
    )
    if sim is None:
        return _error("not_found", "Simulation introuvable.", 404)
    if sim["mode"] != "live" or sim["stopped_at"] is not None:
        return jsonify(queued=0)

    events = (request.get_json(silent=True) or {}).get("events")
    if not isinstance(events, list):
        return _error("invalid_events", "Liste d'événements invalide.", 400)

    now = time.time()
    row = query_one("SELECT COUNT(*) AS n FROM push_queue WHERE sim_id = ?", (sim_id,))
    room = MAX_QUEUED_PER_SIM - (int(row["n"]) if row else 0)
    queued = 0
    for ev in events[:MAX_EVENTS_PER_REQUEST]:
        if queued >= room:
            break
        if not isinstance(ev, dict):
            continue
        try:
            at = float(ev.get("at"))
        except (TypeError, ValueError):
            continue
        key = _clip(ev.get("key"), 80)
        title = _clip(ev.get("title"), 80)
        if not (key and title and now - 300 <= at <= now + 3 * 86400):
            continue
        new_id = execute(
            """INSERT INTO push_queue (user_id, sim_id, event_key, fire_at, title, body, url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (g.user["id"], sim_id, key, at, title, _clip(ev.get("body"), 160), "/sim/%d" % sim_id),
        )
        if new_id is not None:  # None = clé déjà enregistrée
            queued += 1
    return jsonify(queued=queued)


@bp.route("/api/push/dispatch", methods=["GET", "POST"])
def dispatch():
    """Envoie les notifications arrivées à échéance.

    Public mais sans danger : il n'envoie que ce que les utilisateurs ont
    eux-mêmes programmé, chaque ligne est réservée avant l'envoi (pas de
    doublon) et le travail par appel est borné.
    """
    if not _enabled():
        return jsonify(enabled=False, sent=0)

    started = time.time()
    execute(
        "UPDATE push_queue SET sent_at = ?, status = 'stale' WHERE sent_at IS NULL AND fire_at < ?",
        (started, started - STALE_SECONDS),
    )
    due = query_all(
        "SELECT * FROM push_queue WHERE sent_at IS NULL AND fire_at <= ? ORDER BY fire_at LIMIT ?",
        (started, DISPATCH_BATCH),
    )
    sent = failed = skipped = 0
    subs_cache = {}
    for row in due:
        if time.time() - started > DISPATCH_BUDGET_SECONDS:
            break
        claimed = execute(
            "UPDATE push_queue SET sent_at = ?, status = 'claimed' WHERE id = ? AND sent_at IS NULL",
            (time.time(), row["id"]),
        )
        if not claimed:  # un autre appel l'a déjà réservée
            skipped += 1
            continue
        ok, ko = _deliver(
            row["user_id"],
            {"title": row["title"], "body": row["body"], "url": row["url"], "tag": "ev-%d" % row["id"]},
            subs_cache,
        )
        execute(
            "UPDATE push_queue SET status = ? WHERE id = ?",
            ("sent" if ok else ("failed" if ko else "nodevice"), row["id"]),
        )
        sent += ok
        failed += ko
    return jsonify(enabled=True, due=len(due), sent=sent, failed=failed, skipped=skipped)
