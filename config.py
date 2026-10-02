import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_database_url():
    """Trouve l'URL de connexion Postgres quel que soit le nom de variable.

    L'intégration Neon/Vercel Postgres crée des variables préfixées
    (ex. `viralvi_POSTGRES_URL`) ; on gère aussi ce cas.
    On écarte les variantes `PRISMA` (`?pgbouncer=true`, rejeté par libpq)
    et `NO_SSL`. `POSTGRES_URL` (poolée) est privilégiée pour le serverless.
    """
    for name in ("DATABASE_URL", "POSTGRES_URL",
                 "POSTGRES_URL_NON_POOLING", "DATABASE_URL_UNPOOLED"):
        if os.environ.get(name):
            return os.environ[name]

    def _find(suffix, exclude=()):
        for key, val in os.environ.items():
            if key.endswith(suffix) and val and not any(x in key for x in exclude):
                return val
        return None

    return (
        _find("_POSTGRES_URL", exclude=("PRISMA", "NO_SSL"))
        or _find("_POSTGRES_URL_NON_POOLING")
        or _find("_DATABASE_URL_UNPOOLED")
        or _find("_DATABASE_URL", exclude=("UNPOOLED",))
        or ""
    )


class Config:
    # Clé de signature des sessions Flask. On lit d'abord APP_SECRET_KEY /
    # FLASK_SECRET_KEY pour éviter tout conflit avec une variable `SECRET_KEY`
    # déjà occupée par une intégration.
    SECRET_KEY = (
        os.environ.get("APP_SECRET_KEY")
        or os.environ.get("FLASK_SECRET_KEY")
        or os.environ.get("SECRET_KEY")
        or "dev-secret-change-me-in-prod"
    )

    DATABASE_URL = _resolve_database_url()
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Données on-chain réelles (Moralis). Sans clé : l'app reste en mode simulé.
    MORALIS_API_KEY = os.environ.get("MORALIS_API_KEY", "").strip()
    ONCHAIN_CACHE_TTL_SECONDS = int(os.environ.get("ONCHAIN_CACHE_TTL_SECONDS", "1200"))
    # Garde-fou de quota : nombre maximal de wallets interrogés par 24 h.
    ONCHAIN_MAX_FETCHES_PER_DAY = int(os.environ.get("ONCHAIN_MAX_FETCHES_PER_DAY", "250"))

    # Notifications push (Web Push / VAPID). Sans les deux clés : désactivées.
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
    VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "https://viral-vi-drab.vercel.app").strip()
