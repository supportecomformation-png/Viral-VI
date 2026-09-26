from datetime import date

from flask import Flask, render_template, g, jsonify

from config import Config
from db import init_db, query_one
from auth_utils import load_logged_in_user


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    from auth import bp as auth_bp
    from sim import bp as sim_bp, DEMO_TRADERS

    app.register_blueprint(auth_bp)
    app.register_blueprint(sim_bp)

    init_db(app)

    @app.before_request
    def _load_user():
        load_logged_in_user()

    @app.context_processor
    def inject_globals():
        return {
            "current_user": g.get("user"),
            "current_year": date.today().year,
        }

    @app.route("/")
    def landing():
        return render_template("landing.html", traders=DEMO_TRADERS)

    @app.route("/healthz")
    def healthz():
        """Sonde de santé : renvoie 200 si la base répond, 503 sinon."""
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
