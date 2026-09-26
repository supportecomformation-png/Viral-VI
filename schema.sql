-- Schéma PostgreSQL — CopyLab (démo de copy trading, argent fictif)
--
-- `users` est conservée telle quelle (les comptes existants restent valides ;
-- les colonnes plan / stripe_* ne sont plus utilisées). Les anciennes tables
-- de l'app précédente (news_items, scripts) ne sont plus créées ni lues ;
-- si elles existent encore dans ta base, elles sont simplement ignorées.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'inactive',
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
);

-- Une simulation = "l'utilisateur copie ce wallet avec X $ fictifs".
-- Seuls les paramètres sont stockés : l'état (positions, PnL, courbe) est
-- recalculé de façon déterministe côté client à partir de ces paramètres.
CREATE TABLE IF NOT EXISTS simulations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wallet TEXT NOT NULL,
    chain TEXT NOT NULL,                              -- 'solana' | 'evm'
    mode TEXT NOT NULL DEFAULT 'live',                -- 'live' | 'backtest'
    balance DOUBLE PRECISION NOT NULL,                -- solde fictif de départ ($)
    alloc_pct DOUBLE PRECISION NOT NULL,              -- part de l'équité engagée par trade (0-1)
    speed INTEGER NOT NULL,                           -- accélération du temps (x300, x1200, x6000)
    started_at DOUBLE PRECISION NOT NULL,             -- epoch (s), horloge serveur
    stopped_at DOUBLE PRECISION,                      -- epoch (s) si arrêtée manuellement
    created_at TEXT NOT NULL DEFAULT to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
);

CREATE INDEX IF NOT EXISTS idx_simulations_user ON simulations(user_id, id DESC);
