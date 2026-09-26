# CopyLab — simulateur de copy trading (démo, argent fictif)

Application web pour **s'entraîner au copy trading sans risque** : on parcourt un
classement de wallets, on colle l'adresse d'un wallet, et une simulation démarre avec
un solde **fictif**. Aucun dépôt n'est possible, aucun vrai wallet n'est connecté,
aucune transaction réelle n'est passée.

> Anciennement « ViralVI » (générateur de scripts TikTok GTA 6). L'ancienne version est
> conservée dans le tag Git `legacy-gta6-saas`.

## Ce que fait l'app

- **Classement de traders** (7J / 30J, tri par PnL ou win rate) avec courbes de performance.
- **Coller un wallet** (adresse Solana ou EVM `0x…`) : ouvre le profil du wallet et lance la simulation.
- **Simulation de copie** : solde fictif (1 000 / 10 000 / 100 000 $), part du capital par trade
  (5 à 50 %), frais + slippage simulés (0,8 % par côté).
  - *En direct* : le temps est accéléré (×300, ×1 200, ×6 000), les trades du wallet sont copiés
    au fil de l'eau, jusqu'à 90 jours simulés.
  - *Backtest* : rejoue instantanément les 30 derniers jours du wallet.
- Comptes utilisateurs (email + mot de passe) pour enregistrer ses simulations.

## ⚠️ Les données sont simulées

Le « track record » d'un wallet est **généré de façon déterministe à partir de son adresse**
(`static/js/engine.js`) : même adresse → mêmes trades. Ce ne sont **pas** les vraies
transactions du wallet. L'interface l'indique partout. Pour brancher de vraies données
on-chain (Helius, Birdeye, Moralis, Alchemy…), remplacer `tradesBetween()` dans `engine.js`
par un fournisseur qui renvoie les vrais trades ; le reste (simulation, PnL, graphiques)
ne change pas.

## Architecture

```
app.py            factory Flask (routes /, /healthz, 404)
auth.py           inscription / connexion / déconnexion (paramètre ?next=)
auth_utils.py     hash mot de passe, utilisateur courant, @login_required
sim.py            pages (/traders, /trader/<wallet>, /app, /sim/<id>) + API /api/simulations
db.py             accès PostgreSQL (psycopg 3)
schema.sql        tables users + simulations
static/js/engine.js   moteur de simulation déterministe (aussi testable sous Node)
static/js/ui.js       formats, avatars, graphiques SVG
static/js/app.js      logique des pages
tests/engine.test.js  tests du moteur (node tests/engine.test.js)
```

Le serveur ne stocke que les **paramètres** d'une simulation (wallet, solde, part par trade,
vitesse, heure de départ). L'état (positions, PnL, courbe) est recalculé côté client à
partir de ces paramètres : pas de worker, pas de cron, rien de lourd côté serveur.

## Déploiement (Vercel + Postgres)

Variables d'environnement :

| Nom | Rôle |
|---|---|
| `APP_SECRET_KEY` | signature des sessions |
| `DATABASE_URL` (ou `POSTGRES_URL`, y compris préfixée par l'intégration Neon) | base PostgreSQL |

Le schéma est créé automatiquement au premier démarrage (`db.init_db`). Les anciennes
tables de la version GTA 6 (`news_items`, `scripts`) ne sont plus utilisées ; tu peux les
supprimer à la main si tu veux nettoyer la base.

## Lancer en local

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://…" APP_SECRET_KEY="dev"
python app.py    # http://127.0.0.1:5000
node tests/engine.test.js
```
