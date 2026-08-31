-- Schéma PostgreSQL — ViralVI (GTA 6 Script Generator)
-- (migré depuis SQLite pour un déploiement serverless / Vercel + Postgres)

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'inactive',        -- 'inactive' | 'pro' (abonnement actif)
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
);

CREATE TABLE IF NOT EXISTS news_items (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    url TEXT UNIQUE,
    source TEXT,
    tags TEXT,                  -- tags séparés par des virgules
    published_at TEXT NOT NULL, -- ISO date (YYYY-MM-DD)
    created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
);

CREATE TABLE IF NOT EXISTS scripts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    news_id INTEGER REFERENCES news_items(id) ON DELETE SET NULL,
    topic TEXT NOT NULL,
    angle TEXT NOT NULL,
    tone TEXT NOT NULL,
    hook TEXT NOT NULL,
    body TEXT NOT NULL,        -- lignes séparées par \n
    cta TEXT NOT NULL,
    hashtags TEXT NOT NULL,    -- séparés par des espaces
    virality_score INTEGER NOT NULL,
    score_breakdown TEXT NOT NULL, -- JSON
    tips TEXT,                     -- JSON (liste de conseils)
    source_mode TEXT NOT NULL DEFAULT 'template', -- 'template' | 'ai'
    created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
);

CREATE INDEX IF NOT EXISTS idx_scripts_user ON scripts(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at DESC);
