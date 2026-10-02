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

## Notifications push

Lancer une copie peut envoyer sur le téléphone un flux de notifications (achats et ventes du trader copié), une par seconde pendant 20 s, façon pile sur l'écran de verrouillage.

1. Sur la page d'une simulation en direct, le bloc **Notifications** demande l'autorisation et abonne l'appareil (service worker `static/sw.js`, Web Push + VAPID).
2. Quand la copie est lancée, le moteur JS calcule les 20 premiers trades de la simulation (achats et ventes) et les dépose dans la table `push_queue`, à raison d'un par seconde, après 4 s de délai (le temps de verrouiller le téléphone). Constantes `STREAM_COUNT`, `STREAM_GAP`, `STREAM_LEAD` dans `static/js/app.js`.
3. `/api/push/dispatch` envoie chaque notification à son heure : il patiente jusqu'à la suivante (7 s au maximum par appel, la limite d'une fonction serverless est de 10 s) puis passe le relais à un nouvel appel de lui-même (6 relais au plus). Le téléphone peut donc être verrouillé et la page fermée. Tant que l'écran reste allumé, la page relance aussi l'envoi toutes les 6 s en filet de sécurité. Aucun déclencheur externe (cron) n'est nécessaire.
4. L'endpoint est idempotent : chaque ligne est réservée avant l'envoi, jamais de doublon, et une notification en retard de plus de 5 min est abandonnée. Le flux n'est envoyé qu'une fois par simulation. Arrêter ou supprimer la simulation supprime les notifications en attente.

**Mes ventes** (`/ventes`) : onglet à part du copy trading, avec un seul bouton « Lancer la simulation ». Il envoie sur le téléphone une pile de 20 notifications de vente, une par seconde (`POST /api/sales-simulation`, contenu généré côté serveur : « Vente #1001 », montant, nombre d'articles, « MyKingdom (démo) »). Elles portent le nom et le logo de Copy Trade. Constantes `SALES_*` dans `push.py`.

Pour l'activer : définir `VAPID_PUBLIC_KEY` et `VAPID_PRIVATE_KEY` (variables d'environnement Vercel), puis redéployer. Sans elles, le bloc est masqué.
**iPhone** : les notifications web ne fonctionnent qu'une fois le site ajouté à l'écran d'accueil (Partager → Sur l'écran d'accueil), puis ouvert depuis son icône (iOS 16.4 minimum).

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
push.py           notifications push (abonnements, file d'attente, envoi VAPID), /api/push/*
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
