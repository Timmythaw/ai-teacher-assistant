# app.py
import os
import json
from pathlib import Path
from flask import Flask, request, render_template, abort
from werkzeug.utils import secure_filename

# Ensure package imports work
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.assessment_agent import AssessmentAgent  # your existing 
from agents.lesson_plan_agent import LessonPlanAgent

app = Flask(__name__, template_folder="templates", static_folder="static")

# Config
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
ALLOWED_EXTENSIONS = {".pdf"}
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET"])
def index():
    return render_template("base.html")

@app.route("/assessment", methods=["GET"])
def assessment_page():
    return render_template("assessments.html")

@app.route("/lesson-generator", methods=["GET"])
def lesson_generator_page():
    return render_template("lesson_generator.html")

@app.route("/generate-assessment-test", methods=["POST"])
def generate_assessment():
    if "pdf" not in request.files:
        abort(400, description="Missing file field 'pdf'")
    f = request.files["pdf"]
    if f.filename == "":
        abort(400, description="No file selected")
    if not allowed_file(f.filename):
        abort(400, description="Only .pdf files are allowed")

    # Save file
    safe_name = secure_filename(f.filename)
    dest = UPLOAD_DIR / safe_name
    i = 1
    while dest.exists():
        dest = UPLOAD_DIR / f"{dest.stem}_{i}{dest.suffix}"
        i += 1
    f.save(dest.as_posix())

    # Parse options from form
    asmt_type = request.form.get("type", "MCQ")
    difficulty = request.form.get("difficulty", "Medium")
    try:
        count = int(request.form.get("count", "5"))
    except ValueError:
        count = 5
    rubric = request.form.get("rubric") is not None

    # Call your agent with the uploaded PDF path
    agent = AssessmentAgent()
    result = agent.generate_assessment(
        dest.as_posix(),
        {"type": asmt_type, "difficulty": difficulty, "count": count, "rubric": rubric}
    )

    # Return JSON response
    return app.response_class(
        response=json.dumps(result, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json"
    )

@app.route("/generate-lesson-plan", methods=["POST"])
def generate_lesson_plan():
    if "pdf" not in request.files:
        abort(400, description="Missing file field 'pdf'")
    f = request.files["pdf"]
    if f.filename == "":
        abort(400, description="No file selected")
    if not allowed_file(f.filename):
        abort(400, description="Only .pdf files are allowed")

    # Save file
    safe_name = secure_filename(f.filename)
    dest = UPLOAD_DIR / safe_name
    i = 1
    while dest.exists():
        dest = UPLOAD_DIR / f"{dest.stem}_{i}{dest.suffix}"
        i += 1
    f.save(dest.as_posix())

    # Parse options from form
    weeks = 0
    num_stu = 0
    section_per_week = 0

    lp_agent = LessonPlanAgent()
    plan = lp_agent.generate_plan({"course_outline":dest.as_posix()}, weeks, num_stu, section_per_week)
    print(plan)
    
    # Return JSON response
    return app.response_class(
        response=json.dumps(plan, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json"
    )

if __name__ == "__main__":
    # For local dev
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)