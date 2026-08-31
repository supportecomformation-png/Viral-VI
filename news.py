from flask import Blueprint, render_template, request, jsonify, g

from db import query_all, execute

bp = Blueprint("news", __name__, url_prefix="/news")

ADMIN_TOKEN_HEADER = "X-Admin-Token"


@bp.route("/")
def feed():
    items = query_all("SELECT * FROM news_items ORDER BY published_at DESC, id DESC")
    return render_template("news/feed.html", news=items)


@bp.route("/api/refresh", methods=["POST"])
def refresh():
    """
    Endpoint utilisé par scripts/fetch_news.py (cron / GitHub Action) pour
    injecter de nouvelles actus GTA 6 chaque jour. Protégé par un token
    d'admin simple (voir ADMIN_REFRESH_TOKEN dans les variables d'env).
    """
    import os

    expected_token = os.environ.get("ADMIN_REFRESH_TOKEN", "")
    provided_token = request.headers.get(ADMIN_TOKEN_HEADER, "")
    if not expected_token or provided_token != expected_token:
        return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(force=True, silent=True) or {}
    items = payload.get("items", [])
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
            execute(
                """INSERT INTO news_items (title, summary, url, source, tags, published_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (title, summary, url, source, tags, published_at),
            )
            inserted += 1
        except Exception:
            # URL déjà présente (contrainte UNIQUE) -> on ignore silencieusement.
            continue

    return jsonify({"ok": True, "inserted": inserted, "received": len(items)})
