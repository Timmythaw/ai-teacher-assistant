from dotenv import load_dotenv
load_dotenv()  #Importing ENV file 
import os 
from pathlib import Path
from flask import Flask, session, g
from google.oauth2 import id_token
from google.auth.transport import requests

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # configuration
    app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

    # ensure upload directory exists
    UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    app.config["UPLOAD_DIR"] = UPLOAD_DIR

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
    # For local testing of OAuth (remove in production)
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    
    if not google_client_id:
        # It's better to log a warning than crash if you just want to test other parts
        print("WARNING: GOOGLE_CLIENT_ID is not set")

    print("GOOGLE_CLIENT_ID =", google_client_id)

    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)