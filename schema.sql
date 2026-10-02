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

-- Données on-chain : `source` vaut 'simulated' (track record généré) ou 'onchain'
-- (vrais swaps du wallet). Pour 'onchain', `snapshot` fige les trades utilisés au
-- lancement, pour que la simulation reste identique dans le temps.
ALTER TABLE simulations ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'simulated';
ALTER TABLE simulations ADD COLUMN IF NOT EXISTS network TEXT;
ALTER TABLE simulations ADD COLUMN IF NOT EXISTS snapshot TEXT;

CREATE INDEX IF NOT EXISTS idx_simulations_user ON simulations(user_id, id DESC);

-- Cache des trades on-chain par (wallet, réseau) : économise les appels au
-- fournisseur (quota) et alimente le classement des wallets réels analysés.
CREATE TABLE IF NOT EXISTS wallet_cache (
    id SERIAL PRIMARY KEY,
    wallet TEXT NOT NULL,
    network TEXT NOT NULL,
    payload TEXT NOT NULL,
    fetched_at DOUBLE PRECISION NOT NULL,
    UNIQUE (wallet, network)
);

CREATE INDEX IF NOT EXISTS idx_wallet_cache_time ON wallet_cache(fetched_at DESC);

-- Cache des prix des cryptomonnaies (page d'accueil), partagé entre instances.
CREATE TABLE IF NOT EXISTS market_cache (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    fetched_at DOUBLE PRECISION NOT NULL
);

-- Notifications push : appareils abonnés (un utilisateur peut en avoir plusieurs).
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user ON push_subscriptions(user_id);

-- File d'attente : une ligne = une notification à envoyer à `fire_at` (epoch, s).
-- `sent_at` est renseigné dès que la ligne est réservée par un envoi.
CREATE TABLE IF NOT EXISTS push_queue (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sim_id INTEGER NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    event_key TEXT NOT NULL,
    fire_at DOUBLE PRECISION NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '/app',
    sent_at DOUBLE PRECISION,
    status TEXT,
    UNIQUE (sim_id, event_key)
);

CREATE INDEX IF NOT EXISTS idx_push_queue_due ON push_queue(fire_at) WHERE sent_at IS NULL;
