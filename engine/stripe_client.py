"""
Intégration Stripe minimaliste — appels REST directs (pas de SDK requis).

Si STRIPE_SECRET_KEY n'est pas configurée, l'app tourne en "mode démo" :
le bouton "Passer Pro" active directement le plan Pro sans passer par un
vrai paiement, ce qui permet de tester tout le parcours produit avant de
brancher un vrai compte Stripe.
"""

import requests

STRIPE_API_BASE = "https://api.stripe.com/v1"
TIMEOUT_SECONDS = 15


def is_configured(app_config):
    return bool(app_config.get("STRIPE_SECRET_KEY") and app_config.get("STRIPE_PRICE_ID"))


def create_checkout_session(app_config, user_email, success_url, cancel_url, client_reference_id):
    """
    Crée une session Stripe Checkout en mode abonnement.
    Retourne (checkout_url, error).
    """
    secret_key = app_config["STRIPE_SECRET_KEY"]
    price_id = app_config["STRIPE_PRICE_ID"]

    # {CHECKOUT_SESSION_ID} est remplacé par Stripe dans l'URL de retour ;
    # il permet de confirmer le paiement même si le webhook tarde.
    sep = "&" if "?" in success_url else "?"
    data = {
        "mode": "subscription",
        "success_url": f"{success_url}{sep}session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": cancel_url,
        "customer_email": user_email,
        "client_reference_id": str(client_reference_id),
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": 1,
    }

    try:
        resp = requests.post(
            f"{STRIPE_API_BASE}/checkout/sessions",
            data=data,
            auth=(secret_key, ""),
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return None, f"network_error: {exc}"

    if resp.status_code != 200:
        return None, f"stripe_error_{resp.status_code}: {resp.text[:300]}"

    session = resp.json()
    return session.get("url"), None


def retrieve_checkout_session(app_config, session_id):
    """Récupère une session Checkout auprès de Stripe. Retourne (session, error)."""
    secret_key = app_config.get("STRIPE_SECRET_KEY")
    if not secret_key or not session_id:
        return None, "not_configured"
    try:
        resp = requests.get(
            f"{STRIPE_API_BASE}/checkout/sessions/{session_id}",
            auth=(secret_key, ""),
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return None, f"network_error: {exc}"
    if resp.status_code != 200:
        return None, f"stripe_error_{resp.status_code}"
    return resp.json(), None


def verify_and_parse_webhook(payload_body, signature_header, webhook_secret):
    """
    Vérification de signature Stripe simplifiée (HMAC-SHA256, sans
    dépendance au SDK officiel). Pour une prod critique, préférer le SDK
    `stripe` (pip install stripe) qui gère aussi la tolérance temporelle
    et les cas limites plus finement.
    """
    import hmac
    import hashlib
    import time

    if not signature_header:
        return None, "missing_signature"

    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return None, "malformed_signature"

    signed_payload = f"{timestamp}.{payload_body.decode('utf-8')}"
    expected_sig = hmac.new(
        webhook_secret.encode("utf-8"), signed_payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        return None, "signature_mismatch"

    # Tolérance de 5 minutes contre les attaques par rejeu
    if abs(time.time() - int(timestamp)) > 300:
        return None, "timestamp_too_old"

    import json
    try:
        event = json.loads(payload_body)
    except (json.JSONDecodeError, ValueError):
        return None, "invalid_json"

    return event, None
