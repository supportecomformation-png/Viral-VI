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
    from markets import bp as markets_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(sim_bp)
    app.register_blueprint(markets_bp)

    init_db(app)

    @app.before_request
    def _load_user():
        load_logged_in_user()

    @app.context_processor
    def inject_globals():
        return {
            "current_user": g.get("user"),
            "current_year": date.today().year,
            "onchain_enabled": bool(app.config.get("MORALIS_API_KEY")),
        }

    @app.route("/")
    def landing():
        return render_template("home.html", traders=DEMO_TRADERS)

    @app.route("/healthz")
    def healthz():
        """Sonde de santé : renvoie 200 si la base répond, 503 sinon.

        ?timing=1 : mesure (en ms) une connexion neuve puis 3 requêtes, et indique la
        région du serveur de base de données (jamais l'hôte complet ni les identifiants).
        """
        from flask import request
        if request.args.get("timing"):
            return _db_timing()
        try:
            query_one("SELECT 1")
            return jsonify(status="ok")
        except Exception:
            return jsonify(status="degraded"), 503

    def _db_timing():
        import re, time
        from urllib.parse import urlparse
        from db import _connect
        out = {}
        host = urlparse(app.config.get("DATABASE_URL") or "").hostname or ""
        m = re.search(r".([a-z0-9-]+).(?:aws|azure).neon.tech", host)
        out["db_region"] = m.group(1) if m else "inconnue"
        try:
            t0 = time.perf_counter()
            conn = _connect(autocommit=True)
            out["connect_ms"] = round((time.perf_counter() - t0) * 1000)
            times = []
            for _ in range(3):
                t1 = time.perf_counter()
                conn.execute("SELECT 1").fetchone()
                times.append(round((time.perf_counter() - t1) * 1000))
            out["query_ms"] = times
            conn.close()
        except Exception as exc:
            out["error"] = type(exc).__name__
        return jsonify(out)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
