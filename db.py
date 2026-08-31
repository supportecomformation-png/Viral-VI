"""
Accès base de données — PostgreSQL (psycopg 3).

L'app utilisait SQLite à l'origine ; pour un déploiement serverless (Vercel),
le système de fichiers est éphémère et en lecture seule, donc on passe sur
Postgres (Neon / Vercel Postgres / Supabase...).

L'API publique (`query_all`, `query_one`, `execute`) est identique à la version
SQLite pour ne rien changer dans le reste du code. Les requêtes gardent les
placeholders `?` : ils sont traduits en `%s` ici automatiquement.
"""

import re

import psycopg
from psycopg.rows import dict_row
from flask import current_app, g

_PLACEHOLDER_RE = re.compile(r"\?")
_INSERT_RE = re.compile(r"^\s*INSERT\s", re.IGNORECASE)
_RETURNING_RE = re.compile(r"\bRETURNING\b", re.IGNORECASE)


def _dsn():
    dsn = current_app.config.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL n'est pas défini. Renseigne une URL de connexion "
            "PostgreSQL (Neon / Vercel Postgres) dans les variables d'environnement."
        )
    return dsn


def _connect(**kwargs):
    # prepare_threshold=None : désactive les prepared statements, incompatibles
    # avec le pooler PgBouncer en mode transaction (Vercel Postgres poolé).
    kwargs.setdefault("prepare_threshold", None)
    return psycopg.connect(_dsn(), **kwargs)


def get_db():
    if "db" not in g:
        # autocommit : chaque requête est validée immédiatement. Évite qu'une
        # erreur (ex : URL d'actu en doublon) ne bloque la connexion entière,
        # et convient bien au modèle « une requête par invocation » de Vercel.
        g.db = _connect(autocommit=True, row_factory=dict_row)
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def _translate(query):
    return _PLACEHOLDER_RE.sub("%s", query)


SCHEMA_LOCK_KEY = 918273645  # clé arbitraire pour pg_advisory_xact_lock
_schema_ready = False


def init_db(app):
    """Crée les tables si elles n'existent pas. Idempotent, protégé par un
    verrou consultatif pour éviter une course entre plusieurs démarrages à froid.
    Ne s'exécute qu'une fois par process (les invocations suivantes sont no-op)."""
    global _schema_ready
    if _schema_ready:
        return
    import os

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with app.app_context():
        try:
            with _connect(autocommit=False) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(%s)", (SCHEMA_LOCK_KEY,))
                    cur.execute(schema_sql)
                    _seed_initial_news(cur)
                conn.commit()
            _schema_ready = True
        except Exception as exc:  # pragma: no cover - log et on continue
            app.logger.warning("init_db: schéma non appliqué (%s)", exc)

    app.teardown_appcontext(close_db)


def _seed_initial_news(cur):
    """Insère le fil d'actus GTA 6 initial si la table est vide (premier déploiement)."""
    cur.execute("SELECT COUNT(*) FROM news_items")
    if cur.fetchone()[0] > 0:
        return
    try:
        from initial_news import NEWS_ITEMS
    except ImportError:
        return
    for item in NEWS_ITEMS:
        cur.execute(
            """INSERT INTO news_items (title, summary, url, source, tags, published_at)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (url) DO NOTHING""",
            (item["title"], item["summary"], item["url"], item["source"],
             item["tags"], item["published_at"]),
        )


def query_all(query, args=()):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(_translate(query), args)
        return cur.fetchall()


def query_one(query, args=()):
    db = get_db()
    with db.cursor() as cur:
        cur.execute(_translate(query), args)
        return cur.fetchone()


def execute(query, args=()):
    """Exécute une requête d'écriture.

    Pour un INSERT, renvoie l'`id` de la ligne créée (ajoute `RETURNING id`
    si absent). Pour UPDATE/DELETE, renvoie le nombre de lignes affectées.
    En cas de violation d'unicité (ex : URL d'actu déjà présente), renvoie None.
    """
    db = get_db()
    q = _translate(query)
    is_insert = bool(_INSERT_RE.match(q))
    if is_insert and not _RETURNING_RE.search(q):
        q = q.rstrip().rstrip(";") + " RETURNING id"

    try:
        with db.cursor() as cur:
            cur.execute(q, args)
            if is_insert:
                row = cur.fetchone()
                return row["id"] if row else None
            return cur.rowcount
    except psycopg.errors.UniqueViolation:
        return None
