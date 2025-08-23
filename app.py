# app.py
from flask import Flask
from core.config import Config           # <-- your existing config module
from routes import register_blueprints   # <-- new routes pkg

def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)
    register_blueprints(app)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
