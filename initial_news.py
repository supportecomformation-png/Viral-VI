"""
Fil d'actualités GTA 6 initial — infos réelles vérifiées via recherche web
le 31/08/2026.

Ces éléments sont insérés automatiquement au premier démarrage (voir
`db.init_db`) si la table `news_items` est vide, puis complétés chaque jour
par `scripts/fetch_news.py`.
"""

NEWS_ITEMS = [
    {
        "title": "GTA VI : tous les détails dévoilés (romance, PNJ, monde ouvert...)",
        "summary": "Après la diffusion de l'Extended Look, Rockstar a détaillé de nouvelles mécaniques : relations et romance entre les personnages, choix narratifs qui influencent le déroulement de l'histoire, et un monde ouvert présenté comme le plus réactif de la licence.",
        "url": "https://rockstaractu.com/jeux/gta-6/tous-les-details-devoiles",
        "source": "Rockstar Actu",
        "tags": "gameplay, monde ouvert, romance, rockstar",
        "published_at": "2026-08-29",
    },
    {
        "title": "Le 3e Extended Look de GTA 6 diffusé sur Netflix et YouTube",
        "summary": "Rockstar a choisi Netflix comme partenaire de diffusion pour son troisième \"Extended Look\", le 27 août à 15h ET, simultanément disponible sur YouTube. Un format inédit pour l'industrie du jeu vidéo.",
        "url": "https://variety.com/2026/tv/news/gta-6-netflix-trailer-extended-look-release-1236845475/",
        "source": "Variety",
        "tags": "trailer, netflix, extended look",
        "published_at": "2026-08-27",
    },
    {
        "title": "Rockstar réagit aux leaks et s'excuse auprès des joueurs",
        "summary": "Après une nouvelle fuite de séquences de gameplay, Rockstar Games a présenté ses excuses aux joueurs, confirmé que la présentation officielle aurait bien lieu comme prévu, et indiqué que le développement du jeu touchait à sa fin.",
        "url": "https://rockstaractu.com/jeux/gta-6/rockstar-reagit-aux-leaks",
        "source": "Rockstar Actu",
        "tags": "leak, rockstar, communication",
        "published_at": "2026-08-26",
    },
    {
        "title": "Nouvelles images et infos via une preview exclusive du magazine Dazed",
        "summary": "Le magazine Dazed a partagé des visuels inédits de GTA 6 en amont de son numéro de septembre, apportant un nouvel éclairage sur la direction artistique du jeu.",
        "url": "https://rockstaractu.com/jeux/gta-6/preview-dazed",
        "source": "Rockstar Actu",
        "tags": "preview, direction artistique, dazed",
        "published_at": "2026-08-26",
    },
    {
        "title": "Rockstar victime d'un nouveau leak, des images de gameplay circulent",
        "summary": "De nouvelles séquences de gameplay non officielles ont circulé sur les réseaux sociaux après un accès non autorisé, quelques jours avant l'Extended Look officiel.",
        "url": "https://rockstaractu.com/jeux/gta-6/nouveau-leak-aout-2026",
        "source": "Rockstar Actu",
        "tags": "leak, gameplay, securite",
        "published_at": "2026-08-18",
    },
    {
        "title": "Rockstar annonce un Extended Look diffusé le 27 août sur Netflix",
        "summary": "Rockstar a officialisé la date de sa nouvelle présentation gameplay, avec une diffusion événement sur Netflix — une première pour la licence.",
        "url": "https://www.gameblog.fr/jeu-video/ed/news/gta-6-nouvelle-presentation-officialisee-gameplay-trailer-aout-2026-720529",
        "source": "Gameblog",
        "tags": "annonce, netflix, trailer",
        "published_at": "2026-08-06",
    },
    {
        "title": "Les précommandes de GTA 6 sont ouvertes, avec le bonus Vintage Vice City Pack",
        "summary": "Les précommandes ont ouvert le 25 juin 2026 sur les stores PlayStation et Microsoft. Elles incluent un bonus in-game exclusif, le \"Vintage Vice City Pack\".",
        "url": "https://beebom.com/gta-6/#precommandes",
        "source": "Beebom",
        "tags": "precommande, prix, bonus",
        "published_at": "2026-06-25",
    },
    {
        "title": "Date de sortie confirmée : GTA 6 arrive le 19 novembre 2026",
        "summary": "Rockstar Games a confirmé la sortie de GTA 6 pour le 19 novembre 2026 sur PS5, PS5 Pro et Xbox Series X|S, en Édition Standard (80$) et Édition Ultime (100$), prix variables selon les régions.",
        "url": "https://beebom.com/gta-6/#date-de-sortie",
        "source": "Beebom",
        "tags": "date de sortie, prix, ps5, xbox",
        "published_at": "2026-05-15",
    },
    {
        "title": "Leonida, la carte de GTA 6 : deux fois plus grande que Los Santos",
        "summary": "Le jeu se déroule dans l'État fictif de Leonida, avec une version modernisée de Vice City comme ville principale. La carte serait environ deux fois plus grande que celle de GTA V.",
        "url": "https://rockstaractu.com/jeux/gta-6/#leonida",
        "source": "Rockstar Actu",
        "tags": "leonida, vice city, carte, map",
        "published_at": "2026-04-02",
    },
    {
        "title": "Lucia Caminos et Jason Duval : le premier duo jouable de l'histoire de GTA",
        "summary": "GTA 6 introduit ses deux premiers protagonistes jouables simultanément, Lucia Caminos et Jason Duval, un couple de braqueurs inspiré de Bonnie & Clyde, au cœur du scénario.",
        "url": "https://rockstaractu.com/jeux/gta-6/#personnages",
        "source": "Rockstar Actu",
        "tags": "lucia, jason, personnages, scenario",
        "published_at": "2026-03-10",
    },
]
