"""
Moteur de scoring de viralité — ViralVI

Donne un score explicable (0-100) à un script TikTok, décomposé en 6
critères, avec des conseils concrets pour l'améliorer. C'est un modèle
heuristique (pas un ML entraîné sur de la vraie donnée TikTok) : il encode
des règles de copywriting court-format qui reviennent constamment dans le
contenu gaming qui performe (hook fort, tension, rythme, pertinence de
tendance, appel à l'engagement, hashtags ciblés).
"""

import re

CURIOSITY_WORDS = [
    "personne ne parle de", "personne ne sait", "en vrai", "sérieusement",
    "attends", "stop", "arrête", "choc", "choquant", "dingue", "fou",
    "incroyable", "énorme", "exclusif", "exclu", "secret", "caché",
    "jamais vu", "leak", "leaké", "fuite", "révélation", "révèle",
    "personne n'a vu ça", "avant tout le monde", "en avant-première",
    "confirmé", "officiel", "rockstar a", "ils ont osé",
]

EMOTION_WORDS = [
    "hype", "excité", "explosion", "monstrueux", "énorme", "record",
    "historique", "jamais", "impossible", "malaise", "wtf", "omg",
    "cinglé", "parfait", "raté", "déception", "polémique", "clash",
]

CTA_PATTERNS = [
    "commente", "dis-moi", "dis moi", "abonne", "follow", "sauvegarde",
    "enregistre", "partage", "tag un ami", "tague un ami", "et toi",
    "vous en pensez quoi", "qu'en penses-tu", "lequel tu préfères",
    "team lucia", "team jason",
]

TREND_KEYWORDS = [
    "gta 6", "gta vi", "leonida", "vice city", "lucia", "jason",
    "rockstar", "trailer", "bande-annonce", "netflix", "date de sortie",
    "19 novembre", "precommande", "précommande", "leak", "fuite",
    "gameplay", "carte", "map", "prix", "édition", "edition",
]

FILLER_WORDS = ["donc", "en fait", "du coup", "voilà", "genre", "quoi"]


def _count_hits(text_lower, words):
    return sum(1 for w in words if w in text_lower)


def _split_sentences(text):
    parts = re.split(r"[.!?\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def score_hook(hook):
    """0-25 points."""
    hook_lower = hook.lower().strip()
    word_count = len(hook_lower.split())
    score = 0
    notes = []

    # Longueur idéale d'un hook TikTok : 6-14 mots (percutant, se lit en <3s)
    if 5 <= word_count <= 14:
        score += 10
    elif word_count < 5:
        score += 5
        notes.append("Hook un peu court : ajoute un détail concret pour donner du contexte en une phrase.")
    else:
        score += 4
        notes.append("Hook trop long : coupe pour qu'il se lise en moins de 3 secondes (max ~14 mots).")

    # Pattern-interrupt / curiosité
    curiosity_hits = _count_hits(hook_lower, CURIOSITY_WORDS)
    curiosity_pts = min(10, curiosity_hits * 5)
    score += curiosity_pts
    if curiosity_hits == 0:
        notes.append("Ajoute un mot de rupture de pattern (\"Personne ne parle de...\", \"Attends...\") pour stopper le scroll.")

    # Chiffre ou date dans le hook (les chiffres augmentent le CTR)
    if re.search(r"\d", hook):
        score += 3
    else:
        notes.append("Insère un chiffre ou une date (ex : \"19 novembre\", \"3 détails\") : ça booste le CTR.")

    # Question ou tension non résolue
    if "?" in hook or any(w in hook_lower for w in ["ce que", "pourquoi", "comment"]):
        score += 2

    return min(score, 25), notes


def score_emotion(full_text):
    """0-20 points — intensité émotionnelle / tension."""
    text_lower = full_text.lower()
    hits = _count_hits(text_lower, EMOTION_WORDS) + _count_hits(text_lower, CURIOSITY_WORDS)
    score = min(20, hits * 4)
    notes = []
    if score < 8:
        notes.append("Renforce la charge émotionnelle : un mot fort par phrase (dingue, énorme, jamais vu...) maintient l'attention.")
    return score, notes


def score_structure(body_lines):
    """0-20 points — rythme et lisibilité pour un format 20-45s."""
    lines = [l for l in body_lines if l.strip()]
    score = 0
    notes = []

    n = len(lines)
    if 3 <= n <= 6:
        score += 10
    elif n < 3:
        score += 4
        notes.append("Le corps est trop court : vise 3 à 6 punchlines pour tenir 20-45 secondes à l'oral.")
    else:
        score += 6
        notes.append("Trop de lignes : un script TikTok qui performe reste dense, coupe le superflu.")

    # Longueur moyenne des phrases (phrases courtes = meilleur rythme à l'oral)
    lengths = [len(l.split()) for l in lines] or [0]
    avg_len = sum(lengths) / len(lengths)
    if avg_len <= 12:
        score += 6
    elif avg_len <= 18:
        score += 3
    else:
        notes.append("Raccourcis tes phrases (idéal : moins de 12 mots) pour un débit qui claque à l'oral.")

    # Variété de longueur (évite la monotonie)
    if len(set(lengths)) >= max(2, n - 1):
        score += 4

    # Mots de remplissage à éviter
    filler_hits = sum(_count_hits(l.lower(), FILLER_WORDS) for l in lines)
    if filler_hits > 0:
        score = max(0, score - filler_hits)
        notes.append("Supprime les mots de remplissage (\"du coup\", \"en fait\"...) qui diluent le rythme.")

    return min(score, 20), notes


def score_trend_relevance(full_text, extra_tags=None):
    """0-15 points — alignement avec l'actualité GTA 6 du moment."""
    text_lower = full_text.lower()
    hits = _count_hits(text_lower, TREND_KEYWORDS)
    if extra_tags:
        for tag in extra_tags:
            if tag.lower() in text_lower:
                hits += 1
    score = min(15, hits * 3)
    notes = []
    if score < 6:
        notes.append("Ancre le script dans l'actu du jour (cite Leonida, Lucia/Jason, la date du 19 novembre, ou l'actu source) pour capter la recherche du moment.")
    return score, notes


def score_cta(full_text):
    """0-10 points."""
    text_lower = full_text.lower()
    score = 0
    notes = []
    if _count_hits(text_lower, CTA_PATTERNS) > 0:
        score += 7
    else:
        notes.append("Termine par un appel à l'action clair (\"Team Lucia ou Team Jason, dis-le en commentaire\").")
    if "?" in full_text:
        score += 3
    return min(score, 10), notes


def score_hashtags(hashtags):
    """0-10 points."""
    tags = [h for h in hashtags if h.strip()]
    score = 0
    notes = []
    n = len(tags)
    if 3 <= n <= 6:
        score += 6
    elif n > 0:
        score += 3
        notes.append("Vise 3 à 6 hashtags ciblés (ni 1, ni 15) pour maximiser la portée sans paraître spam.")
    else:
        notes.append("Ajoute des hashtags (#GTA6, #GTA6News, #FYP) pour aider l'algorithme à te classer.")

    broad_tags = {"fyp", "foryou", "pourtoi", "viral"}
    niche_tags = {"gta6", "gtavi", "gta6news", "rockstargames", "leonida", "gaming"}
    has_broad = any(t.lower().lstrip("#") in broad_tags for t in tags)
    has_niche = any(t.lower().lstrip("#") in niche_tags for t in tags)
    if has_broad and has_niche:
        score += 4
    elif has_niche:
        score += 2

    return min(score, 10), notes


def compute_virality_score(hook, body_lines, cta, hashtags, extra_tags=None):
    """
    Calcule le score de viralité global (0-100) et son détail par critère.
    Retourne un dict prêt à être sérialisé en JSON pour l'UI.
    """
    full_text = " ".join([hook] + list(body_lines) + [cta])

    hook_score, hook_notes = score_hook(hook)
    emotion_score, emotion_notes = score_emotion(full_text)
    structure_score, structure_notes = score_structure(body_lines)
    trend_score, trend_notes = score_trend_relevance(full_text, extra_tags)
    cta_score, cta_notes = score_cta(full_text)
    hashtag_score, hashtag_notes = score_hashtags(hashtags)

    total = hook_score + emotion_score + structure_score + trend_score + cta_score + hashtag_score
    total = max(0, min(100, round(total)))

    all_notes = hook_notes + emotion_notes + structure_notes + trend_notes + cta_notes + hashtag_notes

    if total >= 85:
        label = "Potentiel viral élevé"
    elif total >= 70:
        label = "Très bon potentiel"
    elif total >= 50:
        label = "Correct — peut être optimisé"
    else:
        label = "Faible — à retravailler"

    breakdown = {
        "hook": {"score": hook_score, "max": 25, "label": "Accroche (hook)"},
        "emotion": {"score": emotion_score, "max": 20, "label": "Tension / émotion"},
        "structure": {"score": structure_score, "max": 20, "label": "Rythme & structure"},
        "trend": {"score": trend_score, "max": 15, "label": "Pertinence actu GTA 6"},
        "cta": {"score": cta_score, "max": 10, "label": "Appel à l'action"},
        "hashtags": {"score": hashtag_score, "max": 10, "label": "Hashtags"},
    }

    return {
        "total": total,
        "label": label,
        "breakdown": breakdown,
        "tips": all_notes[:5],
    }
