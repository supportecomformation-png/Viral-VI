import json

from flask import Blueprint, render_template, request, jsonify, g, current_app

from auth_utils import subscription_required
from db import query_all, query_one, execute
from engine.generator import generate_script_variants, build_variant_from_ai_text
from engine.ai_client import generate_with_ai

bp = Blueprint("dashboard", __name__, url_prefix="/app")

ANGLE_CHOICES = [
    ("", "Laisser ViralVI choisir"),
    ("leak", "Leak / Exclu"),
    ("compte_a_rebours", "Compte à rebours / sortie"),
    ("comparaison", "GTA 5 vs GTA 6"),
    ("personnages", "Lucia & Jason"),
    ("carte", "Carte Leonida"),
    ("prix", "Prix / précommande"),
    ("reaction_trailer", "Réaction trailer / preview"),
]

TONE_CHOICES = [
    ("choc", "Choc / accroche forte"),
    ("humour", "Humour"),
    ("analyse", "Analyse / expert"),
    ("leak_exclu", "Leak exclusif"),
]


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _days_until_release():
    from datetime import date
    release = date(2026, 11, 19)
    delta = (release - date.today()).days
    return max(delta, 0)


@bp.route("/")
@subscription_required
def home():
    news = query_all("SELECT * FROM news_items ORDER BY published_at DESC, id DESC LIMIT 12")
    history = query_all(
        "SELECT * FROM scripts WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
        (g.user["id"],),
    )
    return render_template(
        "dashboard/home.html",
        news=news,
        history=history,
        angle_choices=ANGLE_CHOICES,
        tone_choices=TONE_CHOICES,
        days_left=_days_until_release(),
    )


@bp.route("/generate", methods=["POST"])
@subscription_required
def generate():
    payload = request.get_json(force=True, silent=True) or {}
    topic = (payload.get("topic") or "").strip()
    tone = payload.get("tone") or "choc"
    angle = payload.get("angle") or None
    news_id = _as_int(payload.get("news_id"))
    use_ai = bool(payload.get("use_ai"))
    api_key = (payload.get("api_key") or "").strip()

    news_row = None
    news_summary = None
    news_tags = None
    if news_id:
        news_row = query_one("SELECT * FROM news_items WHERE id = ?", (news_id,))
        if news_row:
            news_summary = news_row["summary"]
            news_tags = [t.strip() for t in (news_row["tags"] or "").split(",") if t.strip()]
            if not topic:
                topic = news_row["title"]

    if not topic:
        return jsonify({"error": "missing_topic", "message": "Indique un sujet ou choisis une actu."}), 400

    ai_error = None
    if use_ai and api_key:
        ai_text, ai_error = generate_with_ai(
            api_key, topic, tone, news_summary=news_summary,
            model=current_app.config["ANTHROPIC_MODEL"],
        )
        if ai_text:
            variant = build_variant_from_ai_text(ai_text, tone=tone, news_tags=news_tags)
            variants = [variant]
        else:
            variants = generate_script_variants(
                topic, tone=tone, angle_key=angle, news_summary=news_summary,
                news_tags=news_tags, days_left=_days_until_release(), n_variants=3,
            )
    else:
        variants = generate_script_variants(
            topic, tone=tone, angle_key=angle, news_summary=news_summary,
            news_tags=news_tags, days_left=_days_until_release(), n_variants=3,
        )

    return jsonify({
        "variants": variants,
        "topic": topic,
        "news_id": news_row["id"] if news_row else None,
        "ai_error": ai_error,
    })


@bp.route("/scripts/save", methods=["POST"])
@subscription_required
def save_script():
    payload = request.get_json(force=True, silent=True) or {}
    variant = payload.get("variant") or {}
    topic = payload.get("topic", "")
    news_id = _as_int(payload.get("news_id"))

    required = ["hook", "body", "cta", "hashtags", "score"]
    if not all(k in variant for k in required):
        return jsonify({"error": "invalid_variant"}), 400

    script_id = execute(
        """INSERT INTO scripts
           (user_id, news_id, topic, angle, tone, hook, body, cta, hashtags,
            virality_score, score_breakdown, tips, source_mode)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            g.user["id"], news_id, topic,
            variant.get("angle_label", variant.get("angle", "")),
            variant.get("tone", ""),
            variant["hook"],
            "\n".join(variant["body"]),
            variant["cta"],
            " ".join(variant["hashtags"]),
            variant["score"]["total"],
            json.dumps(variant["score"]["breakdown"], ensure_ascii=False),
            json.dumps(variant["score"].get("tips", []), ensure_ascii=False),
            variant.get("source_mode", "template"),
        ),
    )
    return jsonify({"ok": True, "script_id": script_id})


@bp.route("/scripts/<int:script_id>/delete", methods=["POST"])
@subscription_required
def delete_script(script_id):
    execute("DELETE FROM scripts WHERE id = ? AND user_id = ?", (script_id, g.user["id"]))
    return jsonify({"ok": True})
