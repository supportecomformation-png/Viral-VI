from datetime import date

from flask import Flask, render_template, g

from config import Config
from db import init_db, query_one, query_all
from auth_utils import load_logged_in_user


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    from auth import bp as auth_bp
    from dashboard import bp as dashboard_bp
    from news import bp as news_bp
    from billing import bp as billing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(billing_bp)

    init_db(app)

    @app.before_request
    def _load_user():
        load_logged_in_user()

    @app.context_processor
    def inject_globals():
        release = date(2026, 11, 19)
        days_left = max((release - date.today()).days, 0)
        return {
            "current_user": g.get("user"),
            "days_left": days_left,
            "current_year": date.today().year,
        }

    @app.route("/")
    def landing():
        news_count = query_one("SELECT COUNT(*) AS c FROM news_items")["c"]
        latest_news = query_all(
            "SELECT * FROM news_items ORDER BY published_at DESC, id DESC LIMIT 4"
        )
        return render_template("landing.html", news_count=news_count, latest_news=latest_news)

    @app.route("/healthz")
    def healthz():
        """Sonde de santé : renvoie 200 si la base répond, 503 sinon."""
        from flask import jsonify
        try:
            query_one("SELECT 1")
            return jsonify(status="ok")
        except Exception:
            return jsonify(status="degraded"), 503

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
