"""
Moteur de génération de scripts TikTok — ViralVI

Deux modes :
  - "template" (par défaut, toujours dispo) : combine des banques de
    hooks / punchlines / CTA taillées pour du contenu GTA 6, en les
    adaptant au sujet fourni (texte libre ou actu sélectionnée).
  - "ai" (optionnel) : si l'utilisateur fournit sa propre clé API
    Anthropic (jamais stockée côté serveur), on demande un script sur
    mesure à Claude puis on le fait passer par le même scoring de
    viralité pour rester cohérent avec le mode template.
"""

import random
import re

from engine.virality import compute_virality_score

ANGLES = {
    "leak": {
        "label": "Leak / Exclu",
        "hooks": [
            "Personne ne parle encore de {sujet}, et c'est une erreur.",
            "Rockstar n'a pas dit ça à voix haute, mais {sujet} confirme tout.",
            "J'ai regardé {sujet} 10 fois avant de vous en parler.",
            "Ce détail sur {sujet} vient de fuiter et personne n'a réagi.",
        ],
        "body": [
            "{sujet}, en 3 secondes : voilà ce que ça change vraiment.",
            "Le detail que tout le monde a zappé : {detail}",
            "Si tu suis GTA 6 depuis le début, ça confirme une théorie qu'on a depuis des mois.",
            "Rockstar n'a jamais confirmé officiellement, mais tout colle.",
        ],
        "ctas": [
            "Tu penses que c'est vrai ou que c'est encore un fake ? Dis-le en commentaire.",
            "Sauvegarde cette vidéo, tu vas en avoir besoin le 19 novembre.",
        ],
        "hashtags": ["#GTA6", "#GTA6News", "#Leak", "#RockstarGames", "#FYP"],
    },
    "compte_a_rebours": {
        "label": "Compte à rebours / sortie",
        "hooks": [
            "Il reste {jours} jours avant GTA 6 et voilà ce qu'on sait sur {sujet}.",
            "GTA 6 sort le 19 novembre. {sujet} change tout ce qu'on pensait savoir.",
            "Compte à rebours GTA 6 : aujourd'hui on parle de {sujet}.",
        ],
        "body": [
            "{sujet}, expliqué en moins de 30 secondes.",
            "{detail}",
            "Et le pire (ou le meilleur), c'est que ce n'est même pas le plus gros détail de la semaine.",
            "Rockstar a confirmé la sortie pour le 19 novembre 2026, sur PS5 et Xbox Series X|S.",
        ],
        "ctas": [
            "Tu précommandes day one ou tu attends les avis ? Dis-moi en commentaire.",
            "Abonne-toi, je poste une actu GTA 6 chaque jour jusqu'à la sortie.",
        ],
        "hashtags": ["#GTA6", "#GTA6News", "#19Novembre", "#RockstarGames", "#FYP"],
    },
    "comparaison": {
        "label": "GTA 5 vs GTA 6",
        "hooks": [
            "GTA 5 vs GTA 6 sur {sujet} : la différence est énorme.",
            "On a comparé {sujet} entre GTA 5 et GTA 6, et ça fait mal.",
            "13 ans séparent GTA 5 de GTA 6. Regarde ce que ça change sur {sujet}.",
        ],
        "body": [
            "En 2013, {sujet} n'existait même pas dans le jeu.",
            "{detail}",
            "Los Santos vs Leonida : la carte de GTA 6 fait presque le double.",
            "Et ce n'est qu'un exemple parmi des dizaines de changements.",
        ],
        "ctas": [
            "Team GTA 5 nostalgique ou team GTA 6 hype ? Commente.",
            "Tag quelqu'un qui doit voir cette comparaison.",
        ],
        "hashtags": ["#GTA6", "#GTA5", "#GTA6News", "#RockstarGames", "#Gaming"],
    },
    "personnages": {
        "label": "Lucia & Jason",
        "hooks": [
            "Lucia et Jason, dans GTA 6, c'est bien plus que Bonnie & Clyde.",
            "{sujet} : ce que ça révèle sur Lucia et Jason.",
            "Premier duo jouable de l'histoire de GTA, et voilà pourquoi ça change tout.",
        ],
        "body": [
            "{sujet}, et ce que ça dit sur leur histoire.",
            "{detail}",
            "Rockstar a confirmé qu'on pourrait switcher entre Lucia et Jason en solo.",
            "Un vrai couple de braqueurs façon Bonnie & Clyde, façon Leonida.",
        ],
        "ctas": [
            "Team Lucia ou team Jason ? Dis-le en commentaire.",
            "Sauvegarde si toi aussi t'es hype pour leur histoire.",
        ],
        "hashtags": ["#GTA6", "#Lucia", "#Jason", "#GTA6News", "#FYP"],
    },
    "carte": {
        "label": "Carte Leonida",
        "hooks": [
            "La carte de GTA 6 (Leonida) sur {sujet}, ça donne le vertige.",
            "{sujet} : un aperçu de la carte la plus grande de l'histoire GTA.",
            "Vice City n'a jamais été aussi grande. Voici {sujet}.",
        ],
        "body": [
            "{sujet}, expliqué simplement.",
            "{detail}",
            "Leonida serait presque deux fois plus grande que Los Santos (GTA 5).",
            "Rockstar promet un monde ouvert vivant, du jamais vu sur la licence.",
        ],
        "ctas": [
            "Quelle zone de la carte tu veux explorer en premier ? Commente.",
            "Abonne-toi pour la suite des infos carte, j'en poste chaque jour.",
        ],
        "hashtags": ["#GTA6", "#Leonida", "#ViceCity", "#GTA6Map", "#FYP"],
    },
    "prix": {
        "label": "Prix / précommande",
        "hooks": [
            "GTA 6 à 80$ ou 100$ : voilà ce que {sujet} change pour toi.",
            "{sujet} : est-ce que ça vaut le prix ?",
            "Précommander GTA 6 day one : bonne ou mauvaise idée après {sujet} ?",
        ],
        "body": [
            "{sujet}, en clair.",
            "{detail}",
            "Édition Standard à 80$, Édition Ultime à 100$, prix variables selon les régions.",
            "Le bonus de précommande inclut le Vintage Vice City Pack.",
        ],
        "ctas": [
            "Tu précommandes ou tu attends les tests ? Dis-le en commentaire.",
            "Partage à quelqu'un qui hésite encore à précommander.",
        ],
        "hashtags": ["#GTA6", "#Precommande", "#GTA6News", "#RockstarGames", "#FYP"],
    },
    "reaction_trailer": {
        "label": "Réaction trailer / preview",
        "hooks": [
            "J'ai regardé {sujet} en boucle, voilà ce que personne n'a vu.",
            "{sujet} vient de sortir et Internet est en PLS.",
            "3 détails cachés dans {sujet} que tu as probablement loupés.",
        ],
        "body": [
            "{sujet}, décrypté image par image.",
            "{detail}",
            "Rockstar glisse toujours des indices dans ses trailers, et celui-là ne fait pas exception.",
            "Certains fans ont déjà repéré des easter eggs liés à GTA 5.",
        ],
        "ctas": [
            "Quel détail t'a le plus marqué ? Dis-le en commentaire.",
            "Sauvegarde cette vidéo avant de rewatch le trailer.",
        ],
        "hashtags": ["#GTA6", "#GTA6Trailer", "#GTA6News", "#RockstarGames", "#FYP"],
    },
}

TONE_INTRO = {
    "choc": ["Attends...", "Stop tout.", "Non mais attends une seconde."],
    "humour": ["Ok il faut qu'on parle sérieusement (ou pas).", "Alerte info complètement absurde :"],
    "analyse": ["Petite analyse rapide :", "Décryptage en 30 secondes :"],
    "leak_exclu": ["Info qui vient de tomber :", "Ça vient de sortir, personne n'en parle encore :"],
}

DEFAULT_DETAIL_FALLBACKS = [
    "Rockstar reste très discret sur les détails techniques, mais chaque indice compte.",
    "C'est le genre de détail qui change complètement la lecture du jeu.",
    "Et ça confirme ce que beaucoup de fans soupçonnaient depuis des mois.",
]


def _clean_topic(topic):
    topic = topic.strip()
    if not topic:
        return "GTA 6"
    return topic[0].upper() + topic[1:] if len(topic) > 1 else topic.upper()


def _pick_detail(news_summary):
    if news_summary and len(news_summary.strip()) > 15:
        # On garde une phrase courte et percutante de l'actu source.
        sentence = re.split(r"(?<=[.!?])\s+", news_summary.strip())[0]
        return sentence[:160]
    return random.choice(DEFAULT_DETAIL_FALLBACKS)


def generate_template_variant(topic, angle_key, tone, news_summary=None, days_left=None, seed=None):
    rng = random.Random(seed)
    angle = ANGLES.get(angle_key, ANGLES["leak"])
    sujet = _clean_topic(topic)
    detail = _pick_detail(news_summary)
    jours = days_left if days_left is not None else "quelques"

    hook_template = rng.choice(angle["hooks"])
    hook = hook_template.format(sujet=sujet, detail=detail, jours=jours)

    intro = rng.choice(TONE_INTRO.get(tone, TONE_INTRO["choc"]))
    body_templates = angle["body"]
    body_lines = [intro] + [
        line.format(sujet=sujet, detail=detail, jours=jours) for line in body_templates
    ]

    cta = rng.choice(angle["ctas"])
    hashtags = list(angle["hashtags"])

    return {
        "angle": angle_key,
        "angle_label": angle["label"],
        "tone": tone,
        "hook": hook,
        "body": body_lines,
        "cta": cta,
        "hashtags": hashtags,
    }


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
            topic, a_key, tone, news_summary=news_summary, days_left=days_left, seed=i * 97 + 13
        )
        score = compute_virality_score(
            variant["hook"], variant["body"], variant["cta"], variant["hashtags"],
            extra_tags=news_tags,
        )
        variant["score"] = score
        variant["source_mode"] = "template"
        variants.append(variant)

    variants.sort(key=lambda v: v["score"]["total"], reverse=True)
    return variants


def build_variant_from_ai_text(ai_text, angle_label="IA personnalisée", tone="choc", news_tags=None):
    """
    Parse un texte libre renvoyé par le modèle IA (format attendu : HOOK,
    lignes de corps, CTA, hashtags séparés par des marqueurs). Reste
    tolérant : si le format n'est pas respecté, on tombe sur un découpage
    simple par lignes.
    """
    hook, body, cta, hashtags = "", [], "", []
    lines = [l.strip() for l in ai_text.strip().split("\n") if l.strip()]

    hashtags = [w for l in lines for w in l.split() if w.startswith("#")]
    lines_wo_hashtags = [l for l in lines if not all(w.startswith("#") for w in l.split())]

    if lines_wo_hashtags:
        hook = lines_wo_hashtags[0]
        if len(lines_wo_hashtags) > 2:
            body = lines_wo_hashtags[1:-1]
            cta = lines_wo_hashtags[-1]
        elif len(lines_wo_hashtags) == 2:
            body = [lines_wo_hashtags[1]]
            cta = "Dis-moi ce que tu en penses en commentaire."
        else:
            body = ["(voir hook)"]
            cta = "Dis-moi ce que tu en penses en commentaire."

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
    }
