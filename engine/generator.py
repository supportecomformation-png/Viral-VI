"""
Moteur de génération de scripts TikTok — ViralVI

Format visé : script "hot take" long (~1400-1700 caractères, 45-70 s à
l'oral), en paragraphes courts d'une à deux phrases, qui pose une
affirmation forte, développe l'argument, reconnaît la nuance, puis
termine sur une question ouverte pour l'engagement.

Deux modes :
  - "template" (par défaut) : assemble un squelette long-format à partir
    de banques de contenu par angle éditorial, adaptées au sujet fourni.
  - "ai" (optionnel) : si l'utilisateur fournit sa propre clé API
    Anthropic (jamais stockée), Claude écrit le script sur mesure ; il
    passe ensuite par le même scoring de viralité.
"""

import random
import re

from engine.virality import compute_virality_score

TARGET_MIN_CHARS = 1350
TARGET_MAX_CHARS = 1750

ANGLES = {
    "leak": {
        "label": "Leak / Exclu",
        "hooks": [
            "Un leak sur {sujet} vient de sortir, et personne n'en parle vraiment.",
            "Ce qu'on vient d'apprendre sur {sujet} change pas mal de choses sur GTA 6.",
            "Personne ne parle encore de {sujet}, et je pense que c'est une erreur.",
        ],
        "premise": "{sujet} pourrait être bien plus important qu'on ne le pensait pour GTA 6.",
        "context": "Depuis les premières infos, on avait tous une idée en tête de ce que ça donnerait.",
        "twist": "Mais ce qui vient de fuiter ne colle pas exactement avec ce qu'on imaginait.",
        "elaboration": "En clair : {detail}",
        "stakes": "Si c'est vrai, ça veut dire que Rockstar a fait des choix qu'on n'avait pas vus venir.",
        "nuance": "Cela dit, un leak reste un leak : rien n'est confirmé officiellement.",
        "measured": "Ce genre de détail peut changer des séquences entières du jeu, ou juste rester anecdotique.",
        "caveat": "Donc ne t'emballe pas trop vite tant que Rockstar n'a rien dit.",
        "rhetorical": "Mais si ça se confirme, pourquoi est-ce que Rockstar n'en a pas parlé plus tôt ?",
        "hashtags": ["#GTA6", "#GTA6News", "#Leak", "#RockstarGames", "#FYP"],
    },
    "compte_a_rebours": {
        "label": "Compte à rebours / sortie",
        "hooks": [
            "Il reste {jours} jours avant GTA 6, et {sujet} vient de tout remettre en question.",
            "GTA 6 sort le 19 novembre, et ce qu'on apprend sur {sujet} n'aide pas à patienter.",
            "À {jours} jours de GTA 6, {sujet} est le détail dont tout le monde devrait parler.",
        ],
        "premise": "{sujet} pourrait être l'élément qui décide si tu précommandes maintenant ou pas.",
        "context": "On sait déjà que le jeu sort le 19 novembre 2026 sur PS5 et Xbox Series.",
        "twist": "Mais plus la date approche, plus certains détails changent la donne.",
        "elaboration": "Concrètement : {detail}",
        "stakes": "À ce stade du développement, chaque info compte parce qu'il n'y aura plus de gros changement.",
        "nuance": "Après, Rockstar garde clairement des choses sous le coude pour la sortie.",
        "measured": "Ça peut être un vrai game changer, comme ça peut être un point de détail gonflé par la hype.",
        "caveat": "Donc reste prudent sur les attentes, on a déjà vu la communauté sur-interpréter.",
        "rhetorical": "La vraie question : est-ce que ça vaut le coup de précommander day one pour ça ?",
        "hashtags": ["#GTA6", "#GTA6News", "#19Novembre", "#RockstarGames", "#FYP"],
    },
    "comparaison": {
        "label": "GTA 5 vs GTA 6",
        "hooks": [
            "Compare {sujet} entre GTA 5 et GTA 6, et l'écart est presque gênant.",
            "13 ans séparent GTA 5 de GTA 6, et {sujet} le montre mieux que tout.",
            "GTA 5 vs GTA 6 sur {sujet} : ce n'est même plus la même licence.",
        ],
        "premise": "{sujet} résume à lui seul le saut de génération entre GTA 5 et GTA 6.",
        "context": "En 2013, on trouvait déjà GTA 5 impressionnant pour l'époque.",
        "twist": "Mais quand tu mets les deux côte à côte aujourd'hui, GTA 5 prend un sacré coup de vieux.",
        "elaboration": "Le point clé : {detail}",
        "stakes": "Ça montre que Rockstar n'a pas juste amélioré le jeu, il a changé d'échelle.",
        "nuance": "Attention quand même : GTA 5 reste une référence, et la nostalgie joue beaucoup.",
        "measured": "Sur le papier c'est le jour et la nuit, mais il faudra voir ce que ça donne manette en main.",
        "caveat": "Et un trailer léché ne dit jamais tout d'un jeu final.",
        "rhetorical": "Du coup, est-ce que GTA 5 va vraiment devenir injouable après GTA 6 ?",
        "hashtags": ["#GTA6", "#GTA5", "#GTA6News", "#RockstarGames", "#Gaming"],
    },
    "personnages": {
        "label": "Lucia & Jason",
        "hooks": [
            "GTA 6 vient peut-être de gâcher l'un de ses meilleurs éléments : {sujet}.",
            "{sujet} : et si Lucia et Jason étaient moins importants qu'on le croyait ?",
            "Premier duo jouable de l'histoire de GTA, et {sujet} soulève un vrai doute.",
        ],
        "premise": "La relation entre Jason et Lucia pourrait être beaucoup moins centrale qu'on l'imaginait.",
        "context": "Depuis le premier trailer, Rockstar nous les montre pourtant comme un vrai couple, complices et prêts à tout l'un pour l'autre.",
        "twist": "Mais le plus surprenant, c'est que {sujet} suggère que ça pourrait rester très optionnel.",
        "elaboration": "En gros : {detail}",
        "stakes": "Rockstar avait une occasion énorme de construire une histoire d'amour profonde, avec des choix qui changent l'aventure.",
        "nuance": "Apparemment, ce ne sera pas aussi extrême que ça.",
        "measured": "Ton lien avec chaque personnage pourrait modifier des dialogues et quelques scènes, sans donner deux jeux complètement différents.",
        "caveat": "Donc ne t'attends probablement pas à un système de relation ultra poussé.",
        "rhetorical": "Jason et Lucia sont censés être au cœur de l'histoire, alors pourquoi laisser le joueur mettre leur relation de côté ?",
        "hashtags": ["#GTA6", "#Lucia", "#Jason", "#GTA6News", "#FYP"],
    },
    "carte": {
        "label": "Carte Leonida",
        "hooks": [
            "{sujet} : la carte de GTA 6 est encore plus grande que ce qu'on pensait.",
            "On a de nouvelles infos sur Leonida grâce à {sujet}, et ça donne le vertige.",
            "Vice City n'a jamais été aussi grande, et {sujet} le prouve.",
        ],
        "premise": "{sujet} laisse penser que Leonida est bien plus dense qu'une simple carte agrandie.",
        "context": "On savait déjà que l'État de Leonida serait environ deux fois plus grand que Los Santos.",
        "twist": "Mais la taille n'est pas vraiment le sujet : c'est ce qu'il y a dedans qui change tout.",
        "elaboration": "Le détail qui compte : {detail}",
        "stakes": "Une grande carte vide, on connaît. Une carte grande ET vivante, c'est une autre histoire.",
        "nuance": "Cela dit, Rockstar en promet beaucoup, et il faudra voir la densité réelle à la sortie.",
        "measured": "Ça peut être le monde ouvert le plus détaillé jamais fait, ou une carte impressionnante mais inégale.",
        "caveat": "Un trailer montre toujours les meilleurs endroits, jamais les zones de transition.",
        "rhetorical": "La vraie question : est-ce qu'on aura envie d'explorer, ou juste de suivre le GPS ?",
        "hashtags": ["#GTA6", "#Leonida", "#ViceCity", "#GTA6Map", "#FYP"],
    },
    "prix": {
        "label": "Prix / précommande",
        "hooks": [
            "GTA 6 entre 80 et 100 dollars, et {sujet} change le calcul.",
            "{sujet} : est-ce que ça vaut vraiment le prix de GTA 6 ?",
            "Avant de précommander GTA 6, il faut parler de {sujet}.",
        ],
        "premise": "{sujet} pourrait être ce qui justifie, ou pas, de mettre 80 à 100 dollars day one.",
        "context": "On connaît déjà les tarifs : Édition Standard autour de 80 dollars, Édition Ultime autour de 100.",
        "twist": "Mais le prix seul ne veut rien dire tant qu'on ne sait pas ce qu'il y a vraiment dans la boîte.",
        "elaboration": "Ce qu'on apprend : {detail}",
        "stakes": "À ce tarif, la moindre déception se paie cher, surtout si tu prends l'édition la plus chère.",
        "nuance": "En face, si le contenu est là, ça reste rentable vu le temps de jeu attendu.",
        "measured": "Le bonus de précommande, le Vintage Vice City Pack, est sympa mais ne devrait pas décider à ta place.",
        "caveat": "Et rappelle-toi qu'attendre quelques semaines te donne les vrais avis des joueurs.",
        "rhetorical": "Donc : tu précommandes maintenant, ou tu attends les tests pour être sûr ?",
        "hashtags": ["#GTA6", "#Precommande", "#GTA6News", "#RockstarGames", "#FYP"],
    },
    "reaction_trailer": {
        "label": "Réaction trailer / preview",
        "hooks": [
            "J'ai regardé {sujet} en boucle, et il y a un truc que personne ne relève.",
            "{sujet} vient de sortir, et un détail mérite beaucoup plus d'attention.",
            "3 visionnages de {sujet} plus tard, voilà ce qui me reste en tête.",
        ],
        "premise": "{sujet} contient un détail qui en dit plus sur le jeu que la plupart des grosses annonces.",
        "context": "Rockstar glisse toujours des indices dans ses trailers, ça a toujours été comme ça.",
        "twist": "Et cette fois, le détail intéressant n'est pas celui que tout le monde a partagé.",
        "elaboration": "Ce que je vois : {detail}",
        "stakes": "Si je ne me trompe pas, ça donne une piste sérieuse sur le ton et le contenu du jeu.",
        "nuance": "Après, on est tous en train de sur-analyser trois secondes de vidéo, faut le reconnaître.",
        "measured": "Ça peut être un vrai indice volontaire, comme un simple élément de décor sans importance.",
        "caveat": "Rockstar sait très bien qu'on décortique tout, donc méfiance sur les fausses pistes.",
        "rhetorical": "Mais si c'est intentionnel, qu'est-ce que Rockstar essaie de nous dire exactement ?",
        "hashtags": ["#GTA6", "#GTA6Trailer", "#GTA6News", "#RockstarGames", "#FYP"],
    },
}

# Amorces émotionnelles selon le ton, insérées en début de corps.
TONE_INTRO = {
    "choc": [
        "Attends deux secondes.",
        "Il faut vraiment qu'on en parle.",
        "Ok, ça, personne ne l'avait vu venir.",
    ],
    "humour": [
        "Bon, on va se dire les choses.",
        "Alerte info à moitié sérieuse, à moitié absurde.",
        "Accroche-toi, c'est un peu n'importe quoi.",
    ],
    "analyse": [
        "Petite analyse à froid.",
        "On prend deux minutes pour décortiquer.",
        "Regardons ça calmement.",
    ],
    "leak_exclu": [
        "Info qui vient de tomber.",
        "Ça circule depuis ce matin, et c'est du lourd.",
        "Personne n'en parle encore, alors je m'y colle.",
    ],
}

# Réactions personnelles qui relancent la tension au milieu du script.
REACTIONS = [
    "Et là, franchement, je suis partagé.",
    "Et c'est exactement ça qui me dérange.",
    "Et plus j'y pense, plus ça me travaille.",
    "Et c'est justement ce point qui me choque.",
]

# Formule "deux côtés" avant la question finale.
BOTH_SIDES = [
    "D'un côté, cette approche est plutôt maligne. Mais de l'autre, j'ai peur qu'on soit déçus le jour de la sortie.",
    "D'un côté, c'est une bonne nouvelle pour la liberté du joueur. De l'autre, ça peut vite ressembler à une occasion manquée.",
    "D'un côté, ça montre l'ambition de Rockstar. De l'autre, l'ambition sur le papier ne suffit pas toujours.",
]

CTAS = [
    "Et toi, tu le vois comment : plutôt hype, ou plutôt méfiant ? Dis-le en commentaire.",
    "Toi tu es team \"on fait confiance à Rockstar\" ou team \"j'attends de voir\" ? Commente.",
    "Tu penses que je surinterprète, ou que j'ai raison de tiquer ? Dis-moi en commentaire.",
    "Et toi, tu préfères la liberté totale, ou des choix avec de vraies conséquences ? Réponds en commentaire.",
]

DEFAULT_DETAIL_FALLBACKS = [
    "Rockstar reste très discret sur les détails, mais tous les indices vont dans le même sens.",
    "c'est le genre d'élément qui change complètement la façon de lire le jeu.",
    "ça confirme ce que pas mal de fans soupçonnaient depuis des mois.",
]


def _clean_topic(topic):
    topic = (topic or "").strip()
    if not topic:
        return "GTA 6"
    return topic[0].upper() + topic[1:] if len(topic) > 1 else topic.upper()


def _pick_detail(news_summary, rng):
    if news_summary and len(news_summary.strip()) > 15:
        sentence = re.split(r"(?<=[.!?])\s+", news_summary.strip())[0].strip()
        sentence = sentence.rstrip(".")
        if len(sentence) > 12:
            return sentence[:200]
    return rng.choice(DEFAULT_DETAIL_FALLBACKS)


def _fill(text, sujet, detail, jours):
    return text.format(sujet=sujet, detail=detail, jours=jours)


def generate_template_variant(topic, angle_key, tone, news_summary=None, days_left=None, seed=None):
    rng = random.Random(seed)
    angle = ANGLES.get(angle_key, ANGLES["leak"])
    sujet = _clean_topic(topic)
    detail = _pick_detail(news_summary, rng)
    jours = days_left if days_left is not None else "quelques"

    hook = _fill(rng.choice(angle["hooks"]), sujet, detail, jours)

    # Squelette long-format : ~15 paragraphes courts.
    body = [
        rng.choice(TONE_INTRO.get(tone, TONE_INTRO["choc"])),
        _fill(angle["premise"], sujet, detail, jours),
        _fill(angle["context"], sujet, detail, jours),
        _fill(angle["twist"], sujet, detail, jours),
        _fill(angle["elaboration"], sujet, detail, jours),
        rng.choice(REACTIONS),
        _fill(angle["stakes"], sujet, detail, jours),
        _fill(angle["nuance"], sujet, detail, jours),
        _fill(angle["measured"], sujet, detail, jours),
        _fill(angle["caveat"], sujet, detail, jours),
        _fill(angle["rhetorical"], sujet, detail, jours),
        rng.choice(BOTH_SIDES),
    ]

    cta = rng.choice(CTAS)
    hashtags = list(angle["hashtags"])

    # Ajuste la longueur pour viser ~1500 caractères.
    body = _fit_length(body, angle, sujet, detail, jours, rng, hook, cta)

    return {
        "angle": angle_key,
        "angle_label": angle["label"],
        "tone": tone,
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": hashtags,
    }


EXTRA_BEATS = [
    "Et honnêtement, c'est le genre de choix qu'on ne pourra juger qu'une fois la manette en main.",
    "Rockstar a l'habitude de nous surprendre là où on ne l'attend pas, donc méfiance.",
    "La communauté va forcément s'enflammer d'ici la sortie, dans un sens comme dans l'autre.",
    "Ce qui est sûr, c'est que ce détail va faire parler bien plus qu'il n'en a l'air.",
    "On en reparlera sûrement quand Rockstar lâchera la prochaine vague d'infos.",
]


def _text_len(hook, body, cta):
    return len(hook) + sum(len(b) for b in body) + len(cta)


def _fit_length(body, angle, sujet, detail, jours, rng, hook, cta):
    total = _text_len(hook, body, cta)
    beats = list(EXTRA_BEATS)
    rng.shuffle(beats)
    # Trop court : on ajoute des "beats" génériques avant la formule de clôture.
    while total < TARGET_MIN_CHARS and beats:
        body.insert(len(body) - 1, beats.pop())
        total = _text_len(hook, body, cta)
    # Trop long : on retire des paragraphes du milieu (jamais le premier ni les 2 derniers).
    while total > TARGET_MAX_CHARS and len(body) > 6:
        body.pop(len(body) - 3)
        total = _text_len(hook, body, cta)
    return body


def generate_script_variants(topic, tone="choc", angle_key=None, news_summary=None,
                              news_tags=None, days_left=None, n_variants=3):
    """
    Génère n variantes de script (angles différents si non imposé), calcule
    le score de viralité de chacune, et les trie par score décroissant.
    """
    angle_keys = list(ANGLES.keys())
    if angle_key and angle_key in ANGLES:
        chosen_angles = [angle_key] * n_variants
    else:
        rng = random.Random()
        chosen_angles = rng.sample(angle_keys, k=min(n_variants, len(angle_keys)))
        while len(chosen_angles) < n_variants:
            chosen_angles.append(rng.choice(angle_keys))

    variants = []
    for i, a_key in enumerate(chosen_angles):
        variant = generate_template_variant(
            topic, a_key, tone, news_summary=news_summary, days_left=days_left,
            seed=i * 97 + 13,
        )
        score = compute_virality_score(
            variant["hook"], variant["body"], variant["cta"], variant["hashtags"],
            extra_tags=news_tags,
        )
        variant["score"] = score
        variant["source_mode"] = "template"
        variant["char_count"] = _text_len(variant["hook"], variant["body"], variant["cta"])
        variants.append(variant)

    variants.sort(key=lambda v: v["score"]["total"], reverse=True)
    return variants


def build_variant_from_ai_text(ai_text, angle_label="IA personnalisée", tone="choc", news_tags=None):
    """
    Parse un texte libre renvoyé par le modèle IA. Format attendu :
    hook en 1re ligne, paragraphes courts séparés par des sauts de ligne,
    CTA en avant-dernière ligne, hashtags en dernière ligne.
    """
    lines = [l.strip() for l in ai_text.strip().split("\n") if l.strip()]

    hashtags = [w for l in lines for w in l.split() if w.startswith("#")]
    lines_wo_hashtags = [l for l in lines if not all(w.startswith("#") for w in l.split())]

    hook, body, cta = "", [], ""
    if lines_wo_hashtags:
        hook = lines_wo_hashtags[0]
        if len(lines_wo_hashtags) > 2:
            body = lines_wo_hashtags[1:-1]
            cta = lines_wo_hashtags[-1]
        elif len(lines_wo_hashtags) == 2:
            body = [lines_wo_hashtags[1]]
            cta = "Et toi, tu en penses quoi ? Dis-le en commentaire."
        else:
            body = ["(voir hook)"]
            cta = "Et toi, tu en penses quoi ? Dis-le en commentaire."

    if not hashtags:
        hashtags = ["#GTA6", "#GTA6News", "#FYP"]

    score = compute_virality_score(hook, body, cta, hashtags, extra_tags=news_tags)

    return {
        "angle": "ai",
        "angle_label": angle_label,
        "tone": tone,
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": hashtags,
        "score": score,
        "source_mode": "ai",
        "char_count": len(hook) + sum(len(b) for b in body) + len(cta),
    }
