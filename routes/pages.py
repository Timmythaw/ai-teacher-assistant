# routes/pages.py
from flask import Blueprint, render_template

bp = Blueprint("pages", __name__)

@bp.get("/")
def index():
    return render_template("base.html")

@bp.get("/assessment")
def assessment_page():
    return render_template("assessments.html")

@bp.get("/lesson-generator")
def lesson_generator_page():
    return render_template("lesson_generator.html")
