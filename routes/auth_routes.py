# routes/auth_routes.py
"""
Authentication Routes using Google OAuth + Supabase Database
Keeps existing Google OAuth flow but adds Supabase for user data storage
"""
import os
import pathlib
from flask import Blueprint, session, abort, redirect, request, url_for, jsonify
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
from utils.supabase_auth import ensure_user_exists_in_db, get_current_user
from flask import Blueprint, session, abort, redirect, request, url_for, jsonify, render_template
from google.oauth2 import id_token

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

# Google OAuth Scopes - All necessary permissions
SCOPES = [
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/calendar",
    "openid",
]


def get_flow():
    """Create Google OAuth flow with redirect URI"""
    redirect_uri = url_for("auth.callback", _external=True)
    flow = Flow.from_client_secrets_file(
        client_secrets_file=CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


# routes/auth_routes.py

@auth_bp.route("/login")
def login():
    """
    Render the Login Page.
    """
    # If already logged in, redirect to dashboard
    if get_current_user():
        return redirect(url_for("main.index"))

    # Just show the HTML page
    return render_template("login.html")


@auth_bp.route("/google")
def google_login():
    """
    Initiate Google OAuth flow.
    This is called when the user clicks "Continue with Google"
    """
    # If already logged in, redirect to dashboard
    if get_current_user():
        return redirect(url_for("main.index"))

    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline",  # Get refresh token
        prompt="consent",  # Force consent screen to get all permissions
    )

    # Store state for CSRF protection
    session["state"] = state

    return redirect(authorization_url)

# ... keep callback, logout, me, and check-google-permissions as they were ...

# You can remove the @auth_bp.route("/verify") function as /login now does this job.


@auth_bp.route("/callback")
def callback():
    """
    Handle Google OAuth callback
    - Verifies authorization
    - Gets user info from Google
    - Creates/updates user in Supabase database
    - Stores user session
    """
    try:
        flow = get_flow()

        # Fetch tokens from Google
        flow.fetch_token(authorization_response=request.url)

        # CSRF protection
        if session.get("state") != request.args.get("state"):
            abort(500, description="State mismatch. Possible CSRF attack.")

        credentials = flow.credentials

        # Verify ID token and get user info
        id_info = id_token.verify_oauth2_token(
            credentials._id_token,
            google.auth.transport.requests.Request(),
            GOOGLE_CLIENT_ID,
        )

        # Store user info in Flask session
        session["google_id"] = id_info.get("sub")
        session["name"] = id_info.get("name")
        session["email"] = id_info.get("email")
        session["picture"] = id_info.get("picture")
        session.permanent = True  # <--- Tells browser to keep you logged in

        # Store Google OAuth credentials for API access
        session["credentials"] = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

        # Create/update user in Supabase database
        user_profile = ensure_user_exists_in_db()

        if not user_profile:
            print(
                f"Warning: Could not create user profile in database for {session['email']}"
            )

        # Check if there's a redirect URL saved before login
        redirect_after_login = session.pop("redirect_after_login", None)
        if redirect_after_login:
            return redirect(redirect_after_login)

        return redirect(url_for("main.index"))

    except Exception as e:
        print(f"OAuth callback error: {e}")
        # Clear any partial session data
        session.clear()
        abort(500, description=f"Authentication failed: {str(e)}")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """
    Logout user
    - Clears Flask session
    - Redirects to login page

    Supports both GET and POST for flexibility
    """
    # Save current page for potential redirect after re-login
    if request.method == "GET":
        session.clear()
        return redirect(url_for("auth.login"))

    # POST request (from JavaScript or form)
    session.clear()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": True, "redirect": url_for("auth.login")}), 200

    return redirect(url_for("auth.login"))


@auth_bp.route("/me")
def get_me():
    """
    Get current authenticated user info
    API endpoint to check authentication status

    Returns:
        JSON with user data or 401 if not authenticated
    """
    user = get_current_user()

    if not user:
        return (
            jsonify(
                {
                    "error": "Not authenticated",
                    "code": "AUTH_REQUIRED",
                    "redirect_to": url_for("auth.login", _external=True),
                }
            ),
            401,
        )

    return jsonify(
        {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "avatar": user["picture"],
        }
    )


# @auth_bp.route("/verify")
# def verify():
#     """
#     Quick endpoint to verify if user is authenticated
#     Used for health checks or quick auth status

#     Returns:
#         JSON with authenticated status
#     """
#     user = get_current_user()
#     has_credentials = session.get("credentials") is not None

#     return jsonify(
#         {
#             "authenticated": user is not None,
#             "user_id": user["id"] if user else None,
#             "has_google_credentials": has_credentials,
#         }
#     )


@auth_bp.route("/check-google-permissions")
def check_google_permissions():
    """
    Check if user has granted all required Google permissions
    Useful for debugging permission issues

    Returns:
        JSON with granted scopes
    """
    user = get_current_user()

    if not user:
        return jsonify({"error": "Not authenticated", "code": "AUTH_REQUIRED"}), 401

    credentials = session.get("credentials", {})
    granted_scopes = credentials.get("scopes", [])

    # Check which required scopes are missing
    missing_scopes = [scope for scope in SCOPES if scope not in granted_scopes]

    return jsonify(
        {
            "user_email": user["email"],
            "granted_scopes": granted_scopes,
            "missing_scopes": missing_scopes,
            "has_all_permissions": len(missing_scopes) == 0,
        }
    )
