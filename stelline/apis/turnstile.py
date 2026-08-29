"""Cloudflare Turnstile token verification."""

import json
import urllib.parse
import urllib.request

from flask import request

from stelline.config import TURNSTILE_SECRET_KEY


def verify_turnstile(token):
    if not TURNSTILE_SECRET_KEY or not token:
        return False

    payload = urllib.parse.urlencode({
        "secret": TURNSTILE_SECRET_KEY,
        "response": token,
        "remoteip": request.remote_addr or "",
    }).encode("utf-8")
    try:
        verify_request = urllib.request.Request(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data=payload,
            method="POST",
        )
        with urllib.request.urlopen(verify_request, timeout=5) as response:
            result = json.load(response)
        return result.get("success") is True
    except (OSError, ValueError, json.JSONDecodeError):
        return False
