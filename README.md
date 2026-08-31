# ViralVI — Générateur de scripts TikTok viraux sur GTA 6

SaaS complet (multi-comptes, abonnements) pour générer des scripts TikTok
sur l'actualité de GTA 6, avec un score de viralité détaillé et un fil
d'actualités renouvelé chaque jour.

⚠️ **Non affilié à Rockstar Games / Take-Two Interactive.** « GTA 6 »,
« Grand Theft Auto » et « Vice City » sont des marques déposées de leurs
propriétaires respectifs. Le nom, le logo et la charte graphique de
ViralVI sont volontairement une création originale *inspirée* de
l'ambiance néon de Vice City — aucun asset officiel n'est utilisé. Garde
ce disclaimer visible sur le site (déjà en pied de page) pour rester dans
un usage de fan/outil communautaire raisonnable.

## Pourquoi Flask (et pas Next.js) ?

C'est un choix pragmatique : Flask + SQLite ne demandent aucune étape de
build front-end, se déploient sur à peu près n'importe quel hébergeur
Python (Render, Railway, Fly.io, PythonAnywhere, VPS classique...), et
toutes les dépendances utilisées (`Flask`, `Werkzeug`, `requests`) sont
minimales et stables. Le code est structuré en blueprints, facile à
migrer vers Postgres ou vers une stack front séparée plus tard si besoin.

## Fonctionnalités

- **Comptes multi-utilisateurs** : inscription / connexion (mot de passe
  hashé, sessions sécurisées), plan Free (5 scripts/mois) et Pro
  (illimité).
- **Générateur de scripts** : sujet libre ou actu du fil, angle éditorial
  (leak, comparaison GTA5/GTA6, personnages, carte, prix, réaction
  trailer...), ton (choc, humour, analyse, leak exclusif). Renvoie 3
  variantes classées par score.
- **Score de viralité (0-100)**, expliqué et actionnable : accroche,
  tension/émotion, rythme, pertinence de l'actu, appel à l'action,
  hashtags — avec des conseils concrets pour chaque script.
- **Mode IA optionnel** : l'utilisateur colle sa propre clé API
  Anthropic (jamais stockée côté serveur — uniquement en mémoire le temps
  de la requête, et en `localStorage` côté navigateur s'il le souhaite)
  pour une génération plus fine sur la même échelle de score.
- **Fil d'actualités GTA 6**, pré-rempli avec 10 actus réelles (vérifiées
  fin août 2026 : sortie le 19 novembre 2026, Extended Look Netflix,
  leaks, carte Leonida, personnages Lucia & Jason...), complété
  automatiquement chaque jour (voir plus bas).
- **Abonnement Stripe** (scaffold complet, mode démo si pas configuré).
- **Design "Vice City Neon"** : palette rose/cyan/violet sur fond
  sombre, entièrement en CSS custom (`static/css/theme.css`), sans
  dépendance à un framework front.

## Base de données

L'app tourne sur **PostgreSQL** (et non plus SQLite) pour permettre un
déploiement serverless. Il te faut une base Postgres : **Neon**
(neon.tech, gratuit), **Vercel Postgres** (onglet Storage du projet
Vercel), Supabase, ou un Postgres local.

Le schéma et le fil d'actus GTA 6 initial sont créés **automatiquement au
premier démarrage** si la base est vide (voir `db.init_db`). Aucune étape
de migration manuelle.

## Démarrage rapide (en local)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"
export SECRET_KEY="une-valeur-aléatoire"

python app.py
# -> http://127.0.0.1:5000
```

## Déploiement sur Vercel

Le projet est prêt pour Vercel (`vercel.json` + `api/index.py`).

1. **Crée une base Postgres** : le plus simple est l'onglet **Storage** du
   projet Vercel → *Create Database* → Postgres. Les variables
   `DATABASE_URL` / `POSTGRES_URL` sont alors injectées automatiquement.
   (Sinon : crée une base sur neon.tech et ajoute `DATABASE_URL` à la
   main dans *Settings → Environment Variables*, en utilisant la chaîne
   **poolée** `...-pooler...`.)
2. **Ajoute les variables d'environnement** (Settings → Environment
   Variables) :
   - `SECRET_KEY` : `python -c "import secrets; print(secrets.token_hex(32))"`
   - `APP_BASE_URL` : `https://ton-projet.vercel.app`
   - `ADMIN_REFRESH_TOKEN` : un token long et secret (pour l'actu quotidienne)
   - Stripe (optionnel) : `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`,
     `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
3. **Déploie** :
   ```bash
   npx vercel login
   npx vercel --prod
   ```
   ou connecte le repo GitHub dans le dashboard Vercel.
4. Au premier chargement, le schéma et les 10 actus GTA 6 sont créés
   automatiquement. Pour re-seeder manuellement une base :
   `vercel env pull .env && python scripts/seed_news.py`.

> Note : `instance/viralvi.sqlite3` (ancienne base SQLite) n'est plus
> utilisé et est exclu du déploiement (`.vercelignore`).

Crée un compte depuis l'interface, génère quelques scripts, et regarde
l'historique se remplir. Sans configuration Stripe, le bouton "Passer
Pro" bascule directement le compte en Pro (mode démo) pour tester tout le
parcours.

## Déploiement sur un autre hébergeur (Render, Railway, VPS...)

L'app reste une appli WSGI classique :

1. `pip install -r requirements.txt gunicorn`
2. `gunicorn -w 4 -b 0.0.0.0:8000 app:app`
3. Variables d'environnement : `DATABASE_URL` (Postgres), `SECRET_KEY`,
   `APP_BASE_URL`, `ADMIN_REFRESH_TOKEN` (voir `.env.example`).
4. Reverse proxy (Nginx ou le load balancer de l'hébergeur) avec HTTPS.

## Brancher Stripe (abonnement Pro)

1. Crée un compte Stripe, un produit "ViralVI Pro" avec un prix récurrent
   mensuel.
2. Renseigne `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`,
   `STRIPE_PUBLISHABLE_KEY`.
3. Crée un endpoint webhook Stripe pointant vers
   `https://ton-domaine/billing/webhook`, écoutant au minimum
   `checkout.session.completed` et `customer.subscription.deleted`.
   Renseigne `STRIPE_WEBHOOK_SECRET` avec le secret fourni par Stripe.
4. Le fichier `engine/stripe_client.py` fait les appels REST directs
   (pas besoin du SDK officiel `stripe`) — pour une vérification de
   signature plus robuste en production critique, tu peux basculer sur
   `pip install stripe` et utiliser `stripe.Webhook.construct_event`.

Sans ces variables, le site reste pleinement fonctionnel en **mode
démo** : personne n'est facturé, mais tu peux tester tout le parcours
Free → Pro.

## Actus GTA 6 automatiques chaque jour

Le fil se rafraîchit tout seul via l'actu GTA 6 de Google News (flux RSS
public, aucune clé API). Les doublons (même URL) sont ignorés.

**Sur Vercel — cron natif (recommandé, déjà configuré).**
`vercel.json` déclare un cron qui appelle `GET /news/api/cron` chaque jour
à 7h UTC. Rien à installer. Pour sécuriser l'endpoint :

1. Génère une valeur aléatoire et ajoute la variable d'environnement
   `CRON_SECRET` (Vercel l'enverra automatiquement dans l'en-tête
   `Authorization: Bearer …` de ses appels cron).
2. Redéploie. Le cron apparaît dans l'onglet **Cron Jobs** du projet ;
   tu peux le déclencher à la main pour tester.

> Plan Hobby : 1 exécution/jour maximum — ce qui correspond exactement au
> besoin ici.

**Autre hébergeur — cron classique :**

```cron
0 8 * * * cd /chemin/vers/viralvi && APP_BASE_URL=https://ton-domaine ADMIN_REFRESH_TOKEN=xxx python3 scripts/fetch_news.py
```

Ce script poste sur `POST /news/api/refresh` (protégé par
`ADMIN_REFRESH_TOKEN`). Aperçu sans rien envoyer :
`python scripts/fetch_news.py --dry-run`.

## Structure du projet

```
app.py                 point d'entrée Flask (factory + routes landing/404)
config.py               configuration (variables d'env)
db.py                    accès SQLite (connexion, requêtes)
schema.sql               schéma de la base
auth.py / auth_utils.py  inscription / connexion / sessions
dashboard.py             générateur, sauvegarde, historique
news.py                  fil d'actus + endpoint d'admin (refresh quotidien)
billing.py               pricing, upgrade, webhook Stripe
engine/
  virality.py            algorithme de scoring (0-100, expliqué)
  generator.py            banques de templates de scripts par angle/ton
  ai_client.py             appel optionnel à l'API Anthropic
  stripe_client.py         appels REST Stripe (checkout + webhook)
scripts/
  seed_news.py             actus réelles initiales (10 items, août 2026)
  fetch_news.py             récupération quotidienne (RSS Google News)
templates/               pages Jinja2
static/css/theme.css      design system "Vice City Neon"
static/js/app.js          génération AJAX, gauge de score, copier/sauver
.github/workflows/        GitHub Action pour l'actu quotidienne
```

## Prochaines étapes suggérées

- Ajouter la vérification d'email et la réinitialisation de mot de passe.
- Passer SQLite → Postgres si tu vises un vrai volume d'utilisateurs.
- Ajouter un vrai back-office admin (actuellement, seul l'endpoint
  `/news/api/refresh` existe côté "admin", protégé par token).
- Ajouter un rate-limiting (ex : Flask-Limiter) sur `/auth/*` et
  `/app/generate` pour éviter les abus.
- Écrire des tests automatisés (le projet a été validé manuellement via
  le client de test Flask — voir historique de la conversation — mais
  aucune suite `pytest` n'est encore committée).
