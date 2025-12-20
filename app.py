from dotenv import load_dotenv

load_dotenv()  # Importing ENV file
import os
from pathlib import Path
import token
from flask import Flask, g
from google.oauth2 import id_token
from google.auth.transport import requests
from datetime import datetime
from utils.db import get_supabase_client
from utils.supabase_auth import get_current_user_id 
from utils.templet_helper import remove_extension


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # connfiguration
    app.config["MAX_CONTENT_LENGTH"] = (
        int(os.environ.get("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024
    )

    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

    # ensure upload directory exists
    UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"] = UPLOAD_DIR
    
    app.template_filter("remove_extension")(remove_extension)  # Add this

    @app.context_processor
    def inject_credits():
        try:
            if not getattr(g, "current_user", None):
                return {"credits": 0}
            user_id = get_current_user_id()
            supabase = get_supabase_client()
            res = ( 
                supabase.table("users")
                .select("credits")
                .eq("id", user_id)
                .single()
                .execute()
            )
            print("inject_credits:", res)
            current_credits = (res.data or {}).get("credits", 0)
        except Exception as e:
            print("inject_credits error:", e)
            current_credits = 0

        return {"credits": current_credits}

    # Custom Jinja2 filter for time formatting
    @app.template_filter("timeago")
    def timeago_filter(timestamp_str):
        """Convert ISO timestamp to relative time like '5 minutes ago'"""
        if not timestamp_str:
            return "Just now"

        try:
            # Handle different timestamp formats
            timestamp_str = str(timestamp_str).strip()

            # Try parsing ISO format with timezone
            if "T" in timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                # Try parsing without timezone
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

            now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()

            diff = now - timestamp
            seconds = abs(diff.total_seconds())  # Use abs to handle future dates

            if seconds < 60:
                return "Just now"
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif seconds < 604800:
                days = int(seconds / 86400)
                return f"{days} day{'s' if days != 1 else ''} ago"
            else:
                weeks = int(seconds / 604800)
                return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        except Exception as e:
            # If all parsing fails, return "Just now" instead of showing error
            print(f"TimeAgo filter error: {e} for timestamp: {timestamp_str}")
            return "Just now"

    # Register datetime format filter
    try:
        from utils.date_helper import register_jinja_filters

        register_jinja_filters(app)
    except Exception as _err:
        # non-critical: if register fails, continue without crashing
        print("Warning: could not register format_datetime filter:", _err)

    # Register blueprints
    from routes.main_routes import main_bp
    from routes.assessment_routes import assessment_bp
    from routes.lesson_plan_routes import lesson_plan_bp
    from routes.batch_routes import batch_bp
    from routes.email_routes import email_bp
    from routes.timetable_routes import timetable_bp
    from routes.auth_routes import auth_bp

    app.register_blueprint(main_bp, url_prefix="/")
    app.register_blueprint(assessment_bp, url_prefix="/assessments")
    app.register_blueprint(lesson_plan_bp, url_prefix="/lesson-plans")
    app.register_blueprint(batch_bp, url_prefix="/batches")
    app.register_blueprint(email_bp, url_prefix="/email")
    app.register_blueprint(timetable_bp, url_prefix="/timetable")
    app.register_blueprint(auth_bp, url_prefix="/auth")

    return app


if __name__ == "__main__":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")

    if not google_client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID is not set")

    print("GOOGLE_CLIENT_ID =", google_client_id)

    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
