"""
Récupère l'actualité GTA 6 du jour depuis Google News (flux RSS public,
aucune clé API requise) et l'envoie à l'endpoint d'admin de l'app pour
alimenter le fil d'actus chaque jour.

À lancer via cron (ex: tous les jours à 8h) ou via la GitHub Action fournie
dans .github/workflows/daily-news.yml.

Variables d'environnement attendues :
  APP_BASE_URL         URL de l'app déployée (ex: https://viralvi.example.com)
  ADMIN_REFRESH_TOKEN  Doit correspondre à la valeur côté serveur

Usage local :
  python scripts/fetch_news.py
  python scripts/fetch_news.py --dry-run   (affiche sans envoyer)
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests

RSS_URL = "https://news.google.com/rss/search?q={query}&hl=fr&gl=FR&ceid=FR:fr"
QUERY = "GTA 6 OR \"GTA VI\" OR \"Grand Theft Auto 6\""

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


def guess_tags(title, summary):
    text = f"{title} {summary}".lower()
    tags = {tag for kw, tag in KEYWORD_TAGS.items() if kw in text}
    tags.add("actualite")
    return ", ".join(sorted(tags))


def parse_rss(xml_text, limit=15):
    root = ET.fromstring(xml_text)
    items = []
    for item_el in root.findall("./channel/item")[:limit]:
        title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        description = (item_el.findtext("description") or "").strip()
        source_el = item_el.find("source")
        source = source_el.text.strip() if source_el is not None and source_el.text else "Google News"
        pub_date_raw = (item_el.findtext("pubDate") or "").strip()

        try:
            published_at = parsedate_to_datetime(pub_date_raw).date().isoformat()
        except (TypeError, ValueError):
            published_at = datetime.utcnow().date().isoformat()

        # La <description> de Google News contient souvent du HTML brut :
        # on ne garde qu'un résumé simple si trop bruité.
        import re
        import html
        clean_summary = html.unescape(re.sub(r"<[^>]+>", "", description)).strip()
        if len(clean_summary) < 20:
            clean_summary = title

        if not title or not link:
            continue

        items.append({
            "title": title,
            "summary": clean_summary[:400],
            "url": link,
            "source": source,
            "tags": guess_tags(title, clean_summary),
            "published_at": published_at,
        })
    return items


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Affiche les résultats sans les envoyer à l'app.")
    args = parser.parse_args()

    resp = requests.get(RSS_URL.format(query=requests.utils.quote(QUERY)), timeout=20)
    resp.raise_for_status()
    items = parse_rss(resp.text)

    if not items:
        print("Aucune actu trouvée.")
        return

    if args.dry_run:
        for it in items:
            print(f"- [{it['published_at']}] {it['title']} ({it['source']})")
        print(f"\n{len(items)} actu(s) trouvée(s) (dry-run, rien envoyé).")
        return

    base_url = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000")
    admin_token = os.environ.get("ADMIN_REFRESH_TOKEN", "")
    if not admin_token:
        print("ADMIN_REFRESH_TOKEN manquant, abandon.", file=sys.stderr)
        sys.exit(1)

    resp = requests.post(
        f"{base_url}/news/api/refresh",
        json={"items": items},
        headers={"X-Admin-Token": admin_token},
        timeout=20,
    )
    resp.raise_for_status()
    print(resp.json())


if __name__ == "__main__":
    main()
