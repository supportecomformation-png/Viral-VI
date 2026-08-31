import os

from flask import Blueprint, render_template, request, jsonify

from db import query_all, execute

bp = Blueprint("news", __name__, url_prefix="/news")

ADMIN_TOKEN_HEADER = "X-Admin-Token"


@bp.route("/")
def feed():
    items = query_all("SELECT * FROM news_items ORDER BY published_at DESC, id DESC")
    return render_template("news/feed.html", news=items)


def _insert_items(items):
    """Insère une liste d'actus, en ignorant les doublons (URL unique)."""
    inserted = 0
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
            new_id = execute(
                """INSERT INTO news_items (title, summary, url, source, tags, published_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, summary, url, source, tags, published_at),
            )
        except Exception:
            continue  # une ligne bancale ne doit pas casser tout le lot
        if new_id:
            inserted += 1
    return inserted


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
    inserted = _insert_items(items)
    return jsonify({"ok": True, "inserted": inserted, "received": len(items)})


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

    inserted = _insert_items(items)
    return jsonify({"ok": True, "inserted": inserted, "fetched": len(items)})
