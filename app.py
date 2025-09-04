# Orchestrator agent import
from agents.orchestra import Orchestrator
# app.py
import os
import io
import csv
from supabase import create_client, Client
import json
from pathlib import Path
from flask import Flask, request, render_template, abort, redirect, url_for, flash
from werkzeug.utils import secure_filename
from integrations.form_response import get_form_full_info
#from datetime import datetime, timezone

# --- Email routes ---
from agents.email_agent import EmailAgent
from flask import jsonify
from integrations.form_creator import create_google_form

# Ensure package imports work
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.assessment_agent import AssessmentAgent  # your existing 
from agents.lesson_plan_agent import LessonPlanAgent
from agents.timetable_agent import TimetableAgent
from integrations.calendar_orchestrator import schedule_from_timetable
from core.md_render import render_assessment_markdown, render_lesson_plan_markdown

app = Flask(__name__, template_folder="templates", static_folder="static")

# Config
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "20")) * 1024 * 1024
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()
ALLOWED_EXTENSIONS = {".pdf"}
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)



url: str = os.environ.get("SUPABASE_URL") or ""
key: str = os.environ.get("SUPABASE_KEY") or ""
supabase: Client = create_client(url, key)

def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

# Orchestrator Chat page
# Orchestrator Chat page
@app.route("/chat", methods=["GET"])
def chat():
    return render_template("chat.html")

# Orchestrator Chat API
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Accepts: multipart/form-data with 'prompt' and optional 'file' (.pdf)
    Returns: { ok, assistant_markdown, ... }
    """
    try:
        prompt = request.form.get('prompt', '').strip()
        file = request.files.get('file')
        options = {}
        file_path = None
        if file and file.filename:
            if not allowed_file(file.filename):
                return jsonify({"ok": False, "error": "Only .pdf files are allowed"}), 400
            # Save uploaded file
            safe_name = secure_filename(file.filename)
            dest = UPLOAD_DIR / safe_name
            i = 1
            while dest.exists():
                dest = UPLOAD_DIR / f"{dest.stem}_{i}{dest.suffix}"
                i += 1
            file.save(dest.as_posix())
            file_path = dest.as_posix()
            # Heuristic: inject file as lesson/assessment input
            if 'lesson' in prompt.lower():
                options['lesson_input'] = {'sources': {'course_outline': file_path}}
            elif 'assessment' in prompt.lower():
                options['assessment_input'] = {'source': file_path, 'spec': {'type': 'MCQ', 'difficulty': 'Medium', 'count': 5, 'rubric': True}}
        # Feature flag to use AutoGen orchestrator when available
        use_autogen = os.environ.get('USE_AUTOGEN', 'false').lower() in {'1','true','yes','on'}
        if use_autogen:
            try:
                from agents.autogen_manager import run_session as ag_run
                ag_state = ag_run(prompt, options=options, persist=False)
                output_md = ag_state.get('assistant_markdown') or 'No output.'
                return jsonify({'ok': True, 'assistant_markdown': output_md, 'state': ag_state}), 200
            except Exception as e:
                # fall through to classic orchestrator if AutoGen fails
                pass

        # Classic orchestrator path; resume across checkpoints to finish
        orch = Orchestrator()
        orch.register_defaults()
        plan = orch.plan(prompt, options=options)
        state = orch.run(plan)
        # Auto-resume if paused to reach render steps
        loops = 0
        while isinstance(state, dict) and (state.get('state') or {}).get('status') == 'paused' and loops < 4:
            state = orch.run(state)
            loops += 1
        # Find markdown output
        md = None
        summary = None
        for t in state.get('tasks', []):
            if t.get('action','').startswith('render_') and isinstance(t.get('result'), str):
                md = t['result']
        for t in state.get('tasks', []):
            if t.get('action') == 'generate_assessment' and isinstance(t.get('result'), dict):
                qn = len(t['result'].get('questions') or [])
                summary = f"### Assessment generated\n\nQuestions: {qn}"
                # If markdown not found, try to render it now
                if not md:
                    from core.md_render import render_assessment_markdown
                    md = render_assessment_markdown(t['result'])
        # Compose output: summary + markdown
        output_md = ''
        if summary:
            output_md += summary + '\n\n'
        if md:
            output_md += md
        if not output_md:
            output_md = 'No output.'
        return jsonify({'ok': True, 'assistant_markdown': output_md, 'state': state}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

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
    if (f.filename or "") == "":
        abort(400, description="No file selected")
    if not allowed_file(f.filename or ""):
        abort(400, description="Only .pdf files are allowed")

    # Save file
    safe_name = secure_filename(f.filename or "")
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

    # Add rendered Markdown into response payload without changing storage shape
    try:
        assessment_md = render_assessment_markdown(assessment)
        # non-destructive: place under a reserved key unlikely to collide
        assessment_with_md = dict(assessment)
        assessment_with_md["_markdown"] = assessment_md
    except Exception:
        assessment_with_md = assessment

    return app.response_class(
        response=json.dumps(assessment_with_md, ensure_ascii=False, indent=2),
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
    
# --- Assessment detail page + helpers ---

@app.route("/assessments/<uuid:assessment_id>", methods=["GET"])
def assessment_detail(assessment_id):
    sel = (
        supabase.table("assessments")
        .select("*")
        .eq("id", str(assessment_id))
        .single()
        .execute()
    )
    asmt = sel.data
    if not asmt:
        return render_template("404.html"), 404

    # pull a few things for header
    title = (
        (asmt.get("result") or {}).get("title")
        or asmt.get("original_filename")
        or "Assessment"
    )
    gf = asmt.get("google_form") or {}
    form_url = gf.get("formUrl")
    form_id  = gf.get("formId")

    return render_template(
        "assessment_detail.html",
        assessment=asmt,
        page_title=title,
        form_url=form_url,
        form_id=form_id,
    )

# ---- API: fetch responses from Google Forms and return JSON (no DB writes) ----
@app.route("/api/assessments/<uuid:assessment_id>/responses", methods=["GET"])
def api_assessment_responses(assessment_id):
    try:
        sel = (
            supabase.table("assessments")
            .select("id, google_form")
            .eq("id", str(assessment_id))
            .single()
            .execute()
        )
        asmt = sel.data
        if not asmt:
            return jsonify({"ok": False, "error": "Assessment not found"}), 404

        gf = asmt.get("google_form") or {}
        form_id_or_link = gf.get("formId") or gf.get("formUrl")
        if not form_id_or_link:
            return jsonify({"ok": False, "error": "No Google Form attached"}), 400

        info = get_form_full_info(form_id_or_link)
        if not info.get("ok"):
            return jsonify({"ok": False, "error": info.get("error", "Failed to fetch")}), 500

        rows = []
        for r in (info.get("responses") or []):
            rows.append({
                "email": r.get("email") or "",
                "submitted": r.get("submitted") or "",
                "score": r.get("totalScore"),
                "fraction": r.get("fraction") or "",
                "percent": r.get("percent"),  # float or None
            })

        return jsonify({
            "ok": True,
            "form_title": info.get("form_title"),
            "max_points": info.get("max_points"),
            "is_quiz": info.get("is_quiz"),
            "num_responses": len(rows),
            "rows": rows,
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    
# Batches Start Here 
@app.route("/api/batches", methods=["GET"])
def api_list_batches():
    """
    Returns [{ id, name, student_count }]
    """
    try:
        res = supabase.table("batches").select("id,name,students(count)").order("name", desc=False).execute()
        batches = []
        for row in (res.data or []):
            cnt = 0
            s = row.get("students")
            if isinstance(s, list) and s:
                cnt = s[0].get("count", 0)
            elif isinstance(s, dict):
                cnt = s.get("count", 0)
            batches.append({"id": row["id"], "name": row.get("name") or "Untitled", "student_count": cnt})
        return jsonify({"ok": True, "batches": batches}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/batches/<id>/students", methods=["GET"])
def api_list_students(id):
    """
    Returns [{ id, name, email }] for the batch
    """
    try:
        res = supabase.table("students").select("name,email").eq("batch_id", id).order("name", desc=False).execute()
        return jsonify({"ok": True, "students": res.data or []}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/email/send-batch", methods=["POST"])
def api_email_send_batch():
    """
    Body:
    {
      "batch_id": "uuid",
      "subject": "string",
      "notes": "string",
      "tone": "string"        # default "professional, friendly"
      "action": "send"|"draft",  # default "send"
      "assessment_id": "uuid"    # optional: if present, we try to include google_form.formUrl
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        batch_id = (data.get("batch_id") or "").strip()
        subject = (data.get("subject") or "").strip()
        notes = data.get("notes") or ""
        tone = (data.get("tone") or "professional, friendly").strip()
        action = (data.get("action") or "send").strip().lower()
        assessment_id = (data.get("assessment_id") or "").strip()

        if action not in ("send", "draft"):
            action = "send"
        if not batch_id:
            return jsonify({"ok": False, "error": "batch_id is required"}), 400
        if not subject:
            return jsonify({"ok": False, "error": "subject is required"}), 400

        # If an assessment_id is provided, try to fetch its Google Form URL
        form_url = None
        if assessment_id:
            try:
                sel = supabase.table("assessments").select("google_form").eq("id", assessment_id).single().execute()
                gf = (sel.data or {}).get("google_form") if sel and sel.data else None
                if isinstance(gf, dict):
                    form_url = gf.get("formUrl")
            except Exception:
                # Non-fatal: we just skip adding a link
                form_url = None

        # Append the form link to the notes if available
        if form_url:
            # add a clear separator for readability
            notes = (notes.strip() + "\n\nGoogle Form: " + form_url).strip()

        # fetch students
        stu_res = supabase.table("students").select("name,email").eq("batch_id", batch_id).execute()
        students = stu_res.data or []
        if not students:
            return jsonify({"ok": False, "error": "No students found for this batch"}), 404

        agent = EmailAgent()  # requires credentials.json + token.json at project root
        results, sent, drafted, failed = [], 0, 0, 0

        for s in students:
            name = (s.get("name") or "").strip()
            email = (s.get("email") or "").strip()
            if not email:
                results.append({"ok": False, "student_id": s.get("id"), "error": "Missing email"})
                failed += 1
                continue

            prompt = f"""to: {email}
to_name: {name}
subject: {subject}
tone: {tone}
action: {action}
notes: {notes}
"""

            try:
                r = agent.run(prompt, default_use_html=True)
                ok = r.get("ok", False)
                results.append({
                    "ok": ok,
                    "student_id": s.get("id"),
                    "to": email,
                    "mode": r.get("mode"),
                    "error": r.get("error")
                })
                if ok and r.get("mode") == "send":
                    sent += 1
                elif ok and r.get("mode") == "draft":
                    drafted += 1
                else:
                    failed += 1
            except Exception as e:
                results.append({"ok": False, "student_id": s.get("id"), "to": email, "error": str(e)})
                failed += 1

        return jsonify({
            "ok": True,
            "summary": {"total": len(students), "sent": sent, "drafted": drafted, "failed": failed},
            "results": results
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# Student in Batch 

@app.route("/batches/<string:batch_id>", methods=["GET"])
def batch_show(batch_id):
    bres = supabase.table("batches")\
        .select("id,name")\
        .eq("id", batch_id)\
        .single()\
        .execute()
    batch = bres.data
    if not batch:
        return render_template("404.html"), 404

    sres = supabase.table("students")\
        .select("student_id,name,email")\
        .eq("batch_id", batch_id)\
        .order("name")\
        .execute()
    students = sres.data or []

    return render_template("batch_students.html", batch=batch, students=students)



# Lesson Plans start here 
@app.route("/generate-lesson-plan", methods=["POST"])
def generate_lesson_plan():
    if "course_outline" not in request.files:
        abort(400, description="Missing file field 'pdf'")
    f = request.files["course_outline"]
    if (f.filename or "") == "":
        abort(400, description="No file selected")
    if not allowed_file(f.filename or ""):
        abort(400, description="Only .pdf files are allowed")

    # Save file
    safe_name = secure_filename(f.filename or "")
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
    # Attach rendered markdown for convenience (clients may drop it before saving)
    try:
        plan_md = render_lesson_plan_markdown(plan) if isinstance(plan, dict) and not plan.get("error") else None
        plan_with_md = dict(plan)
        if plan_md is not None:
            plan_with_md["_markdown"] = plan_md
    except Exception:
        plan_with_md = plan

    # Return JSON response
    return app.response_class(
        response=json.dumps(plan_with_md, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json"
    )

# --- Lesson Plans: list & save ---

@app.route("/lesson-plans", methods=["GET"])
def lesson_plans_list():
    try:
        res = supabase.table("lesson_plans") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(50) \
            .execute()
        lesson_plans = res.data or []
        return render_template("lesson_plans_list.html", lesson_plans=lesson_plans)
    except Exception as e:
        # fail soft to empty list
        return render_template("lesson_plans_list.html", lesson_plans=[], error=str(e)), 200


@app.route("/api/lesson-plans", methods=["POST"])
def save_lesson_plan():
    """
    Body JSON:
    {
      "original_filename": "...",   # optional
      "pdf_path": "...",            # optional (local path you saved)
      "options": {...},             # weeks, students, sections, etc
      "result": {...}               # lesson plan JSON (the thing you render)
    }
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = payload.get("result")

        if not isinstance(result, dict):
            return jsonify({"ok": False, "error": "Invalid payload: missing result object"}), 400

        row = {
            "original_filename": payload.get("original_filename"),
            "pdf_path": payload.get("pdf_path"),
            "options": payload.get("options"),
            "result": result
        }

        db_res = supabase.table("lesson_plans").insert(row).execute()

        saved = (db_res.data or [None])[0]
        return jsonify({"ok": True, "id": saved["id"] if saved else None, "saved": saved}), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/lesson-plans/<uuid:id>/markdown", methods=["GET"])
def lesson_plan_markdown(id):
    try:
        sel = supabase.table("lesson_plans").select("result").eq("id", str(id)).single().execute()
        row = sel.data or {}
        result = row.get("result")
        if not isinstance(result, dict):
            return jsonify({"ok": False, "error": "Lesson plan not found or invalid JSON"}), 404
        md = render_lesson_plan_markdown(result)
        return jsonify({"ok": True, "markdown": md}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# Email Sendings Start Here 

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
    # If insertion failed, data may be empty; handle gracefully
    if not batch_id:
        flash("Failed to create batch", "error")
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
    #if students_to_insert:
        #students_resp = supabase.table("students").insert(students_to_insert).execute()
    

    return redirect(url_for("batches_page"))


# Timetable APIs (used by lesson_generator.html)
@app.route("/api/timetable/suggest", methods=["POST"])
def api_timetable_suggest():
    """
    Body JSON:
    {
      "plan": { ... },                 # lesson plan JSON (server strips _markdown)
      "slot_hours": 1,                 # optional, int
      "work_hours": [9, 17],           # optional, [startHour, endHour]
      "calendar_id": "primary",       # optional
      "location_hint": "Room 101"     # optional
    }
    Returns { ok, suggested_slots: [...], metadata: {...} }
    """
    try:
        data = request.get_json(silent=True) or {}
        plan = data.get("plan")
        if not isinstance(plan, dict):
            return jsonify({"ok": False, "error": "Missing or invalid plan JSON"}), 400

        slot_hours = int(data.get("slot_hours") or 1)
        work_hours = data.get("work_hours") or [9, 17]
        if not (isinstance(work_hours, (list, tuple)) and len(work_hours) == 2):
            work_hours = [9, 17]
        calendar_id = (data.get("calendar_id") or "primary").strip() or "primary"
        location_hint = data.get("location_hint")

        agent = TimetableAgent()
        res = agent.suggest_consistent_schedule(
            plan,
            slot_hours=slot_hours,
            work_hours=(int(work_hours[0]), int(work_hours[1])),
            calendar_id=calendar_id,
            location_hint=location_hint,
        )
        if not isinstance(res, dict) or res.get("error"):
            return jsonify({"ok": False, "error": res.get("error", "Failed to suggest timetable")}), 500

        return jsonify({
            "ok": True,
            "suggested_slots": res.get("suggested_slots") or [],
            "metadata": res.get("metadata") or {},
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/timetable/schedule", methods=["POST"])
def api_timetable_schedule():
    """
    Body JSON:
    { "timetable": { suggested_slots: [...], metadata: {...} } }
    Returns { ok, results: [...], summary: {...} }
    """
    try:
        data = request.get_json(silent=True) or {}
        tt = data.get("timetable")
        if not isinstance(tt, dict) or "suggested_slots" not in tt:
            return jsonify({"ok": False, "error": "Missing timetable.suggested_slots"}), 400

        results = schedule_from_timetable(tt)
        if not isinstance(results, list):
            return jsonify({"ok": False, "error": "Scheduling failed"}), 500

        total = len(results)
        ok_count = sum(1 for r in results if r.get("ok"))
        failed = total - ok_count
        first_link = None
        for r in results:
            link = r.get("html_link") or r.get("htmlLink")
            if r.get("ok") and link:
                first_link = link
                break

        return jsonify({
            "ok": True,
            "results": results,
            "summary": {"total": total, "inserted": ok_count, "failed": failed},
            "first_link": first_link,
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # For local dev
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)