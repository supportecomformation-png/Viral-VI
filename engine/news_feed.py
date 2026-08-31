"""
Récupération de l'actualité GTA 6 depuis le flux RSS public de Google News
(aucune clé API requise).

Utilisé par :
  - le cron Vercel (route GET /news/api/cron) — rafraîchissement quotidien
  - scripts/fetch_news.py — usage manuel / cron classique
"""

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

RSS_URL = "https://news.google.com/rss/search?q={query}&hl=fr&gl=FR&ceid=FR:fr"
QUERY = 'GTA 6 OR "GTA VI" OR "Grand Theft Auto 6"'

KEYWORD_TAGS = {
    "trailer": "trailer",
    "bande-annonce": "trailer",
    "leak": "leak",
    "fuite": "leak",
    "date de sortie": "date de sortie",
    "précommande": "precommande",
    "precommande": "precommande",
    "gameplay": "gameplay",
    "carte": "carte",
    "map": "carte",
    "leonida": "leonida",
    "vice city": "vice city",
    "lucia": "personnages",
    "jason": "personnages",
    "netflix": "netflix",
    "prix": "prix",
    "rockstar": "rockstar",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def clean_title(title):
    """Retire le suffixe « - Éditeur » que Google News ajoute à chaque titre."""
    title = _WS_RE.sub(" ", title).strip()
    for sep in (" - ", " — ", " | "):
        head, found, tail = title.rpartition(sep)
        if found and head and len(tail) <= 45:
            return head.strip()
    return title


def guess_tags(title, summary):
    text = f"{title} {summary}".lower()
    tags = {tag for kw, tag in KEYWORD_TAGS.items() if kw in text}
    tags.add("actualite")
    return ", ".join(sorted(tags))


def parse_rss(xml_text, limit=15):
    root = ET.fromstring(xml_text)
    items = []
    for item_el in root.findall("./channel/item")[:limit]:
        raw_title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        description = (item_el.findtext("description") or "").strip()
        source_el = item_el.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else "Google News"
        pub_date_raw = (item_el.findtext("pubDate") or "").strip()

        if not raw_title or not link:
            continue

        title = clean_title(raw_title)

        try:
            published_at = parsedate_to_datetime(pub_date_raw).date().isoformat()
        except (TypeError, ValueError):
            published_at = datetime.now(timezone.utc).date().isoformat()

        summary = _WS_RE.sub(" ", html.unescape(_TAG_RE.sub("", description))).strip()
        # Le flux "search" de Google News ne fournit souvent qu'un écho du titre
        # comme description : dans ce cas on garde un résumé propre et lisible.
        if len(summary) < len(title) + 15 or title.lower() in summary.lower():
            summary = f"{title}. À suivre sur {source}."

        items.append({
            "title": title,
            "summary": summary[:400],
            "url": link,
            "source": source,
            "tags": guess_tags(title, summary),
            "published_at": published_at,
        })
    return items


def fetch_gta6_news(limit=15, timeout=15):
    """Renvoie la liste des actus GTA 6 les plus récentes (dicts prêts à insérer)."""
    url = RSS_URL.format(query=requests.utils.quote(QUERY))
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return parse_rss(resp.text, limit=limit)
