# routes/auth_routes.py
import os
import pathlib
from flask import Blueprint, session, abort, redirect, request, url_for
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests

auth_bp = Blueprint("auth", __name__)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "840970484260-h2rmsrj3obau562fg7ngg1131o6ne3bt.apps.googleusercontent.com",
)

CLIENT_SECRETS_FILE = os.path.join(
    pathlib.Path(__file__).parent.parent,
    "client_secret.json",
)

SCOPES = [
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/calendar",
    "openid",
]

def get_flow():
    redirect_uri = url_for("auth.callback", _external=True)
    flow = Flow.from_client_secrets_file(
        client_secrets_file=CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow

@auth_bp.route("/login")
def login():
    flow = get_flow()
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)

@auth_bp.route("/callback")
def callback():
    flow = get_flow()
    flow.fetch_token(authorization_response=request.url)

    # CSRF protection
    if session.get("state") != request.args.get("state"):
        abort(500)

    credentials = flow.credentials

    # Debug: print what audience you expect
    print("GOOGLE_CLIENT_ID =", GOOGLE_CLIENT_ID, flush=True)

    # Verify token and get user info
    id_info = id_token.verify_oauth2_token(
        credentials._id_token,
        google.auth.transport.requests.Request(),
        GOOGLE_CLIENT_ID,
    )

    # Debug: see what audience is actually in the token
    print("id_info['aud'] =", id_info.get("aud"), flush=True)

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    session["email"] = id_info.get("email")
    session["picture"] = id_info.get("picture")

    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }

    return redirect(url_for("main.index"))

@auth_bp.route("/logout")
def logout():
    """Logout user and clear session."""
    session.clear()
    return redirect(url_for("main.index"))



def login_required(f):
    """Decorator to protect routes that require authentication."""
    from functools import wraps


    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "google_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)


    return decorated_function