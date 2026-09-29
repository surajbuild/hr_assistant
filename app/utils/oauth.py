"""
app/utils/oauth.py
------------------
Google OAuth 2.0 / OIDC configuration using Authlib.

Provides the configured `oauth` registry for initiating the authorization-code
flow and exchanging authorization codes for tokens.
"""

import os
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")

oauth = OAuth()

oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
    access_token_url="https://oauth2.googleapis.com/token",
    userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
    jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
    client_kwargs={
        "scope": "openid email profile",
        "claims_options": {
            "iss": {"values": ["https://accounts.google.com", "accounts.google.com"]}
        },
    },
)
