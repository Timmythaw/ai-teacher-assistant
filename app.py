# app.py
import os
import json
from pathlib import Path
from flask import Flask, request, render_template, abort
from werkzeug.utils import secure_filename
# --- Email routes ---
from agents.email_agent import EmailAgent
from flask import jsonify
from integrations.form_creator import create_google_form

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
    if not isinstance(result, dict) or "questions" not in result:
        return app.response_class(
            response=json.dumps({"ok": False, "error": result.get("error", "Invalid assessment result"), "assessment": result}, ensure_ascii=False, indent=2),
            status=400,
            mimetype="application/json"
        )

    # Optional: create a Google Form if user checked the box
    create_form = request.form.get("create_form") is not None
    form_info = None
    if create_form:
        # Title can use the filename or a friendly fallback
        title = f"Assessment - {Path(dest).stem}"
        form_info = create_google_form(result, title=title)
        # You can add basic status normalization
        if isinstance(form_info, dict) and form_info.get("success"):
            result["_google_form"] = {
                "formId": form_info.get("formId"),
                "formUrl": form_info.get("formUrl"),
                "questionCount": form_info.get("questionCount")
            }
        else:
            # Include error from create_google_form so the UI can show it
            result["_google_form_error"] = form_info

    # Return JSON response
    return app.response_class(
        response=json.dumps(result, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json"
    )

@app.route("/generate-lesson-plan", methods=["POST"])
def generate_lesson_plan():
    if "course_outline" not in request.files:
        abort(400, description="Missing file field 'pdf'")
    f = request.files["course_outline"]
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
    weeks = 8
    num_stu = 20
    section_per_week = 1

    lp_agent = LessonPlanAgent()
    plan = lp_agent.generate_plan({"course_outline":dest.as_posix()}, weeks, num_stu, section_per_week)
    print(plan)

    # Return JSON response
    return app.response_class(
        response=json.dumps(plan, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json"
    )

@app.route("/email", methods=["GET"])
def email_page():
    return render_template("email.html")

@app.route("/email/compose", methods=["POST"])
def email_compose():
    """
    Accepts a simple form and builds a prompt for EmailAgent.
    Fields: to_email, subject, notes, tone, action (send|draft), cc, bcc
    """
    to_email = (request.form.get("to_email") or "").strip()
    subject = request.form.get("subject") or ""
    notes = request.form.get("notes") or ""
    tone = request.form.get("tone") or "professional, friendly"
    action = (request.form.get("action") or "send").strip().lower()
    cc = (request.form.get("cc") or "").strip()
    bcc = (request.form.get("bcc") or "").strip()

    # Build a structured prompt so parse_prompt_to_fields can extract everything
    prompt = f"""to: {to_email}
subject: {subject}
tone: {tone}
action: {action}
cc: {cc}
bcc: {bcc}
notes: {notes}
"""

    try:
        agent = EmailAgent()  # will init Gmail service; needs credentials.json
        result = agent.run(prompt, default_use_html=True)
        status = 200 if result.get("ok") else 400
        return app.response_class(
            response=json.dumps(result, ensure_ascii=False, indent=2),
            status=status,
            mimetype="application/json",
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    # For local dev
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)