import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-prod")

    # URL de connexion PostgreSQL (Vercel Postgres / Neon / Supabase...).
    # Vercel Postgres injecte plusieurs variables ; on prend la première utile.
    # NB : POSTGRES_PRISMA_URL est ignoré (contient `?pgbouncer=true`, rejeté
    # par libpq). POSTGRES_URL est déjà la chaîne poolée, idéale en serverless.
    DATABASE_URL = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRES_URL_NON_POOLING")
        or os.environ.get("DATABASE_URL_UNPOOLED")
        or ""
    )
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # Plans
    FREE_PLAN_MONTHLY_CREDITS = 5
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
