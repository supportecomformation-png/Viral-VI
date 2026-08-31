"""
Appel optionnel à l'API Anthropic pour une génération plus fine.

Important : la clé API est fournie par l'utilisateur à chaque requête
(champ du formulaire, jamais persistée en base de données ni journalisée)
et transite uniquement le temps de l'appel HTTP. Si aucune clé n'est
fournie, ou si l'appel échoue, l'appelant doit retomber sur le mode
"template" (voir engine/generator.py).
"""

import requests

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
TIMEOUT_SECONDS = 25

SYSTEM_PROMPT = (
    "Tu es un scénariste spécialisé dans les scripts TikTok viraux pour la "
    "communauté gaming francophone, expert de l'actualité de GTA 6 "
    "(Rockstar Games, sortie le 19 novembre 2026, map Leonida/Vice City, "
    "personnages Lucia Caminos et Jason Duval). Tu écris des scripts "
    "courts (20-45 secondes à l'oral), avec un hook percutant en première "
    "ligne, 3 à 5 punchlines courtes, puis un appel à l'action, puis une "
    "ligne de hashtags. Réponds UNIQUEMENT avec le script, une ligne par "
    "élément, sans numérotation ni explication."
)


def generate_with_ai(api_key, topic, tone, news_summary=None, model="claude-sonnet-4-5-20250929"):
    """
    Retourne (texte_genere: str, error: str|None).
    """
    if not api_key:
        return None, "no_api_key"

    context = f"\nContexte actu source : {news_summary}" if news_summary else ""
    user_prompt = (
        f"Sujet : {topic}\n"
        f"Ton souhaité : {tone}\n"
        f"{context}\n\n"
        "Écris le script maintenant (hook, punchlines, CTA, hashtags)."
    )

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        resp = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return None, f"network_error: {exc}"

    if resp.status_code != 200:
        return None, f"api_error_{resp.status_code}"

    data = resp.json()
    blocks = data.get("content", [])
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    if not text:
        return None, "empty_response"

    return text, None
