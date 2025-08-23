# app.py
import os
import io
import csv
from supabase import create_client, Client
import json
from pathlib import Path
from flask import Flask, request, render_template, abort, redirect, url_for, flash
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



url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET"])
def index():
    return render_template("base.html")

@app.route("/assessments")
def assessments_list():
    res = supabase.table("assessments").select("*").order("created_at", desc=True).execute()
    assessments = res.data if res.data else []
    return render_template("assessments_list.html", assessments=assessments)


@app.route("/assessment-generate", methods=["GET"])
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

    # Parse options
    asmt_type = request.form.get("type", "MCQ")
    difficulty = request.form.get("difficulty", "Medium")
    try:
        count = int(request.form.get("count", "5"))
    except ValueError:
        count = 5
    rubric = request.form.get("rubric") is not None

    # Generate
    agent = AssessmentAgent()
    assessment = agent.generate_assessment(
        dest.as_posix(),
        {"type": asmt_type, "difficulty": difficulty, "count": count, "rubric": rubric}
    )
    if not isinstance(assessment, dict) or "questions" not in assessment:
        return app.response_class(
            response=json.dumps(
                {"ok": False, "error": assessment.get("error", "Invalid assessment result")},
                ensure_ascii=False, indent=2
            ),
            status=400,
            mimetype="application/json"
        )

    return app.response_class(
        response=json.dumps(assessment, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json"
    )

@app.route("/api/assessments", methods=["POST"])
def save_assessment():
    """
    Body:
    {
      "original_filename": "...",   # optional
      "pdf_path": "...",            # optional
      "options": {...},             # what you sent to the agent
      "result": {...},              # assessment JSON
      "google_form": null           # should be null at this stage
    }
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = payload.get("result")

        if not isinstance(result, dict) or "questions" not in result:
            return jsonify({"ok": False, "error": "Invalid payload: missing result.questions"}), 400

        row = {
            "original_filename": payload.get("original_filename"),
            "pdf_path": payload.get("pdf_path"),
            "options": payload.get("options"),
            "result": result,
            "google_form": payload.get("google_form"),  # usually None now
        }

        db_res = supabase.table("assessments").insert(row).execute()
        if getattr(db_res, "error", None):
            return jsonify({"ok": False, "error": str(db_res.error)}), 500

        saved = db_res.data[0] if db_res.data else None
        return jsonify({"ok": True, "id": saved["id"] if saved else None, "saved": saved}), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/assessments", methods=["GET"])
def list_assessments():
    try:
        res = supabase.table("assessments").select("*").order("created_at", desc=True).limit(50).execute()
        return app.response_class(
            response=json.dumps(res.data or [], ensure_ascii=False, indent=2),
            status=200, mimetype="application/json"
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/assessments/<uuid:id>/create-form", methods=["POST"])
def create_form_for_assessment(id):
    try:
        # 1) fetch row
        sel = supabase.table("assessments").select("*").eq("id", str(id)).single().execute()
        row = sel.data
        if not row:
            return jsonify({"ok": False, "error": "Assessment not found"}), 404

        assessment = row.get("result")
        if not isinstance(assessment, dict) or "questions" not in assessment:
            return jsonify({"ok": False, "error": "Row has no valid assessment JSON"}), 400

        title = f"Assessment - {row.get('original_filename') or 'Untitled'}"

        # 2) create Google Form
        form_info = create_google_form(assessment, title=title)
        if not isinstance(form_info, dict) or not form_info.get("success"):
            return jsonify({"ok": False, "error": form_info.get("error", "Failed to create form")}), 500

        # 3) update row with google_form
        upd = supabase.table("assessments") \
            .update({"google_form": form_info}) \
            .eq("id", str(id)).execute()

        updated = upd.data[0] if upd.data else None
        return jsonify({"ok": True, "google_form": form_info, "updated": updated}), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


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

@app.route('/batches')
def batches_page():
    response = supabase.table('batches')\
        .select('id, name, students(count)')\
        .execute()

    batches = response.data if response.data else []

    # Render template passing batches
    return render_template('course_batches.html', batches=batches)



@app.route("/add-new-batch", methods=["POST"])
def create_batch_upload_csv():
    batch_name = request.form.get("batch_name")
    file = request.files.get("students_csv")

    if not batch_name or not file:
        flash("Batch name and CSV file are required.", "error")
        return redirect(url_for("courses_batches"))

    # Read CSV content
    stream = io.StringIO(file.stream.read().decode("utf-8"))
    csv_reader = csv.DictReader(stream)

    # Insert batch into Supabase 'batches' table and get batch id
    batch_resp = supabase.table("batches").insert({"name": batch_name}).execute()


    batch_id = batch_resp.data[0]["id"] if batch_resp.data else None
    if hasattr(batch_resp, 'error') and batch_resp.error:
        flash("Failed to create batch: " + str(batch_resp.error), "error")
        return redirect(url_for("courses_batches"))

    # Prepare list of students to insert
    students_to_insert = []
    for row in csv_reader:
        name = row.get("name")
        email = row.get("email")
        if not name or not email:
            continue  # skip invalid row
        students_to_insert.append({
            "batch_id": batch_id,
            "name": name,
            "email": email,
        })

    # Insert students if any
    if students_to_insert:
        students_resp = supabase.table("students").insert(students_to_insert).execute()
    

    return redirect(url_for("batches_page"))

if __name__ == "__main__":
    # For local dev
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)