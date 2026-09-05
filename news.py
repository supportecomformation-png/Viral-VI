import os
from datetime import datetime, timezone

from flask import Blueprint, render_template, request, jsonify

from db import query_all, query_one, execute

bp = Blueprint("news", __name__, url_prefix="/news")

ADMIN_TOKEN_HEADER = "X-Admin-Token"

# Le cron Vercel est censé rafraîchir le fil chaque jour, mais son
# déclenchement n'est pas garanti à 100% (plan, config, incident Vercel...).
# Filet de sécurité : si la dernière actu insérée est trop vieille, une
# requête normale sur le fil déclenche elle-même un rafraîchissement.
STALE_AFTER_HOURS = 20


def _self_heal_if_stale():
    try:
        row = query_one("SELECT created_at FROM news_items ORDER BY created_at DESC LIMIT 1")
        if not row or not row.get("created_at"):
            return
        created = datetime.strptime(row["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        if age_hours < STALE_AFTER_HOURS:
            return

        from engine.news_feed import fetch_gta6_news
        # Timeout court : ce fetch se produit dans une requête utilisateur
        # normale, il ne doit pas risquer de dépasser le timeout de la fonction.
        _insert_items(fetch_gta6_news(timeout=6))
    except Exception:
        pass  # le fil d'actus ne doit jamais faire planter une page normale


@bp.route("/")
def feed():
    _self_heal_if_stale()
    items = query_all("SELECT * FROM news_items ORDER BY published_at DESC, id DESC")
    return render_template("news/feed.html", news=items)


def _insert_items(items):
    """Insère (ou met à jour, si l'URL existe déjà) une liste d'actus."""
    processed = 0
    for item in items:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        summary = (item.get("summary") or "").strip()
        source = (item.get("source") or "").strip()
        tags = (item.get("tags") or "").strip()
        published_at = (item.get("published_at") or "").strip()

        if not title or not url or not published_at:
            continue

        try:
            execute(
                """INSERT INTO news_items (title, summary, url, source, tags, published_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT (url) DO UPDATE SET
                     title = EXCLUDED.title,
                     summary = EXCLUDED.summary,
                     source = EXCLUDED.source,
                     tags = EXCLUDED.tags""",
                (title, summary, url, source, tags, published_at),
            )
        except Exception:
            continue  # une ligne bancale ne doit pas casser tout le lot
        processed += 1
    return processed


@bp.route("/api/refresh", methods=["POST"])
def refresh():
    """
    Endpoint utilisé par scripts/fetch_news.py (cron classique / GitHub Action)
    pour injecter de nouvelles actus GTA 6. Protégé par ADMIN_REFRESH_TOKEN.
    """
    expected_token = os.environ.get("ADMIN_REFRESH_TOKEN", "")
    provided_token = request.headers.get(ADMIN_TOKEN_HEADER, "")
    if not expected_token or provided_token != expected_token:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(force=True, silent=True) or {}
    items = payload.get("items", [])
    processed = _insert_items(items)
    return jsonify({"ok": True, "upserted": processed, "received": len(items)})


@bp.route("/api/cron", methods=["GET", "POST"])
def cron_refresh():
    """
    Rafraîchissement quotidien automatique, déclenché par le cron Vercel
    (voir la clé "crons" dans vercel.json).

    Autorisation acceptée si :
      - l'en-tête `Authorization: Bearer <CRON_SECRET>` correspond (envoyé
        automatiquement par Vercel quand la variable CRON_SECRET est définie), ou
      - l'en-tête `X-Admin-Token` correspond à ADMIN_REFRESH_TOKEN (déclenchement manuel).
    """
    cron_secret = os.environ.get("CRON_SECRET", "")
    admin_token = os.environ.get("ADMIN_REFRESH_TOKEN", "")

    auth_header = request.headers.get("Authorization", "")
    authorized = False
    if cron_secret and auth_header == f"Bearer {cron_secret}":
        authorized = True
    elif admin_token and request.headers.get(ADMIN_TOKEN_HEADER, "") == admin_token:
        authorized = True

    if not authorized:
        return jsonify({"error": "unauthorized"}), 401

    from engine.news_feed import fetch_gta6_news

    try:
        items = fetch_gta6_news()
    except Exception as exc:  # réseau / RSS indisponible
        return jsonify({"error": "fetch_failed", "detail": str(exc)}), 502

    processed = _insert_items(items)
    return jsonify({"ok": True, "upserted": processed, "fetched": len(items)})
