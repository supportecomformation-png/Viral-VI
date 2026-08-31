"""Point d'entrée Vercel (fonction serverless Python).

Vercel sert la variable WSGI `app` exposée ici. Toutes les routes sont
redirigées vers ce fichier via `vercel.json`.
"""

import os
import sys

# Rend les modules du projet (app.py, db.py, engine/...) importables.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402  — Vercel sert cette variable WSGI

__all__ = ["app"]
