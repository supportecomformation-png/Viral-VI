"""
Récupère l'actualité GTA 6 du jour (Google News RSS) et l'envoie à l'app.

En production sur Vercel, ce n'est PAS nécessaire : un cron Vercel appelle
directement /news/api/cron chaque jour (voir "crons" dans vercel.json).

Ce script reste utile pour :
  - un déclenchement manuel : python scripts/fetch_news.py
  - un aperçu sans rien envoyer : python scripts/fetch_news.py --dry-run
  - un cron classique sur un serveur non-Vercel

Variables d'environnement (hors --dry-run) :
  APP_BASE_URL         URL de l'app déployée
  ADMIN_REFRESH_TOKEN  doit correspondre à la valeur côté serveur
"""

import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import requests  # noqa: E402

from engine.news_feed import fetch_gta6_news  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Affiche les résultats sans les envoyer à l'app.")
    args = parser.parse_args()

    items = fetch_gta6_news()
    if not items:
        print("Aucune actu trouvée.")
        return

    if args.dry_run:
        for it in items:
            print(f"- [{it['published_at']}] {it['title']} ({it['source']})")
        print(f"\n{len(items)} actu(s) trouvée(s) (dry-run, rien envoyé).")
        return

    base_url = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    admin_token = os.environ.get("ADMIN_REFRESH_TOKEN", "")
    if not admin_token:
        print("ADMIN_REFRESH_TOKEN manquant, abandon.", file=sys.stderr)
        sys.exit(1)

    resp = requests.post(
        f"{base_url}/news/api/refresh",
        json={"items": items},
        headers={"X-Admin-Token": admin_token},
        timeout=20,
    )
    resp.raise_for_status()
    print(resp.json())


if __name__ == "__main__":
    main()
