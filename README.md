# CopyLab — simulateur de copy trading (démo, argent fictif)

Application web pour **s'entraîner au copy trading sans risque** : on parcourt un
classement de wallets, on colle l'adresse d'un wallet, et une simulation démarre avec
un solde **fictif**. Aucun dépôt n'est possible, aucun vrai wallet n'est connecté,
aucune transaction réelle n'est passée.

> Anciennement « ViralVI » (générateur de scripts TikTok GTA 6). L'ancienne version est
> conservée dans le tag Git `legacy-gta6-saas`.

## Ce que fait l'app

- **Accueil** (`/`) : solde fictif avec bouton « Déposer » (argent fictif stocké dans le navigateur, aucun paiement), meilleurs traders de la semaine, et liste des 250 premières cryptomonnaies avec prix en dollars, variation 24 h, favoris (étoile), recherche et filtres (Cryptomonnaies, Tendances, Plus échangés, Baisses), actualisée toutes les 30 s.
- **Classement de traders** (7J / 30J, tri par PnL ou win rate) avec courbes de performance.
- **Coller un wallet** (adresse Solana ou EVM `0x…`) : ouvre le profil du wallet et lance la simulation.
- **Copie d'un wallet** : un écran de saisie du montant façon FOMO (gros montant, boutons rapides 50 / 100 / 500 / 1 500 $, pavé numérique ou clavier). Le montant (1 à 1 000 000 $, argent fictif) devient le capital de la simulation ; 10 % du capital est engagé par trade copié, frais + slippage simulés (0,8 % par côté). Le temps est accéléré (×6 000) : les trades du wallet sont copiés au fil de l'eau, jusqu'à 90 jours simulés. L'écran de copie ne contient que la saisie du montant ; le PnL 30 jours du wallet est rappelé en haut à droite.
- Comptes utilisateurs (email + mot de passe) pour enregistrer ses simulations.

## Données : simulées par défaut, on-chain réelles avec une clé Moralis

**Sans clé API** : les performances des wallets sont **simulées** (générées de façon déterministe
à partir de l'adresse, `static/js/engine.js`). L'interface l'indique partout.

**Avec `MORALIS_API_KEY`** : pour toute adresse collée (hors traders vedettes), CopyLab lit les
**vrais swaps DEX** du wallet sur 30 jours (Solana + réseaux EVM : Base, Ethereum, BNB Chain,
Arbitrum, Polygon, Optimism) via l'API Moralis, et reconstitue des trades :

- un trade = un cycle achat(s) → vente(s) sur un même token, du premier achat à la sortie complète ;
- rendement réalisé = valeur vendue / coût d'achat − 1, en dollars au moment des swaps ;
- seuls les trades **clôturés** dans la fenêtre comptent (les positions encore ouvertes sont listées
  sans valorisation) ; une vente sans achat connu dans la fenêtre est ignorée ; les swaps entre
  monnaies de référence (SOL→USDC…) sont ignorés ; cycles < 5 $ ignorés ;
- la courbe entre l'entrée et la sortie d'un trade est **interpolée** (seules l'entrée et la sortie sont réelles) ;
- la copie rejoue ces trades réels en temps accéléré (ou instantanément) avec ton solde fictif.

Garde-fous : résultats mis en cache 20 min par (wallet, réseau) dans `wallet_cache`, plafond de
`ONCHAIN_MAX_FETCHES_PER_DAY` wallets analysés par 24 h (défaut 250, ~50 CU par page Moralis), et
chaque simulation on-chain **fige un instantané** des trades utilisés. Si le fournisseur échoue,
l'interface affiche l'erreur : elle ne bascule **jamais** silencieusement sur des données inventées.
Le classement « Wallets réels analysés » liste les wallets récemment analysés (≥ 5 trades), triés
par ROI réalisé.

Les 12 « traders vedettes » restent des adresses fictives au track record simulé.

## Architecture

```
app.py            factory Flask (routes /, /healthz, 404)
auth.py           inscription / connexion / déconnexion (paramètre ?next=)
auth_utils.py     hash mot de passe, utilisateur courant, @login_required
sim.py            pages (/traders, /trader/<wallet>, /app, /sim/<id>) + API /api/simulations
db.py             accès PostgreSQL (psycopg 3)
schema.sql        tables users + simulations
onchain.py        fournisseur Moralis, swaps → trades, cache et quota
markets.py        prix des cryptos (CoinGecko, repli CoinPaprika), cache 60 s, /api/markets
static/js/engine.js   moteur de simulation (trades simulés ou réels), testable sous Node
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
| `MORALIS_API_KEY` *(optionnel)* | active les vraies données on-chain (clé gratuite sur moralis.com) |
| `ONCHAIN_MAX_FETCHES_PER_DAY` *(optionnel, défaut 250)* | plafond de wallets analysés par 24 h |
| `ONCHAIN_CACHE_TTL_SECONDS` *(optionnel, défaut 1200)* | durée du cache par wallet |

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
