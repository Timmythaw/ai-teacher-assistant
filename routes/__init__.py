# routes/__init__.py
from flask import Flask
from .pages import bp as pages_bp
from .assessments import bp as assessments_bp
from .lessons import bp as lessons_bp

def register_blueprints(app: Flask) -> None:
    app.register_blueprint(pages_bp)
    app.register_blueprint(assessments_bp)
    app.register_blueprint(lessons_bp)
