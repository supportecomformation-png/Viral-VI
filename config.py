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
    # déjà occupée par une intégration (Stripe, etc.).
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

    # Abonnement unique (payant)
    PRO_PLAN_PRICE_EUR = 19

    # Stripe (optionnel — l'app tourne en "mode démo" si absent)
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")

    # IA optionnelle (l'utilisateur colle sa propre clé côté navigateur —
    # jamais stockée en base). Modèle utilisé si une clé est fournie :
    ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
