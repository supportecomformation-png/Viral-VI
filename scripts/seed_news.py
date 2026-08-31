"""
(Ré)initialise le fil d'actualités GTA 6 dans la base PostgreSQL.

En principe inutile : l'app insère ce fil automatiquement au premier
démarrage (voir `db.init_db` -> `_seed_initial_news`) si la table est vide.
Ce script sert à re-seeder manuellement une base fraîche.

Usage :
    vercel env pull .env          # récupère DATABASE_URL depuis Vercel
    python scripts/seed_news.py

Pour la suite, `scripts/fetch_news.py` (cron ou GitHub Action, voir
.github/workflows/daily-news.yml) complète ce fil chaque jour.
"""

import os
import sys

import psycopg

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from initial_news import NEWS_ITEMS  # noqa: E402

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
    or os.environ.get("POSTGRES_URL_NON_POOLING")
    or os.environ.get("DATABASE_URL_UNPOOLED")
    or ""
)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]


def main():
    if not DATABASE_URL:
        sys.exit(
            "DATABASE_URL manquant. Récupère-le depuis Vercel "
            "(`vercel env pull .env`) ou exporte-le, puis relance ce script."
        )

    schema_path = os.path.join(BASE_DIR, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    inserted = 0
    with psycopg.connect(DATABASE_URL, autocommit=True, prepare_threshold=None) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_sql)

        for item in NEWS_ITEMS:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO news_items (title, summary, url, source, tags, published_at)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (url) DO NOTHING""",
                    (item["title"], item["summary"], item["url"], item["source"],
                     item["tags"], item["published_at"]),
                )
                if cur.rowcount and cur.rowcount > 0:
                    inserted += cur.rowcount

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM news_items")
            total = cur.fetchone()[0]

    print(f"{inserted} actu(s) insérée(s). Total en base : {total}.")


if __name__ == "__main__":
    main()
