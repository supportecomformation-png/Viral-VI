import hashlib
import os
from datetime import date

from flask import Flask, render_template, g, jsonify, request, send_from_directory, url_for

from config import Config
from db import init_db, query_one
from auth_utils import load_logged_in_user


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    from auth import bp as auth_bp
    from sim import bp as sim_bp, DEMO_TRADERS
    from markets import bp as markets_bp
    from push import bp as push_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(sim_bp)
    app.register_blueprint(markets_bp)
    app.register_blueprint(push_bp)

    init_db(app)

    _asset_versions = {}

    def asset(path):
        """URL d'un fichier statique avec une empreinte de contenu (?v=…).

        Le CDN peut ainsi le garder en cache un an : l'URL change dès que le fichier change.
        """
        version = _asset_versions.get(path)
        if version is None:
            try:
                with open(os.path.join(app.static_folder, path), "rb") as f:
                    version = hashlib.sha1(f.read()).hexdigest()[:10]
            except OSError:
                version = ""
            _asset_versions[path] = version
        url = url_for("static", filename=path)
        return "%s?v=%s" % (url, version) if version else url

    app.jinja_env.globals["asset"] = asset

    @app.after_request
    def _cache_static(resp):
        # Fichiers versionnés (?v=empreinte) : cache navigateur + CDN d'un an.
        if request.endpoint == "static" and request.args.get("v"):
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

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

    @app.route("/sw.js")
    def service_worker():
        # Doit être servi à la racine pour contrôler tout le site ; jamais mis en cache.
        resp = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
        resp.headers["Cache-Control"] = "no-cache"
        resp.headers["Service-Worker-Allowed"] = "/"
        return resp

    @app.route("/manifest.webmanifest")
    def manifest():
        resp = send_from_directory(app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

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
