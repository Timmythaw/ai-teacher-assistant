# routes/assessment_routes.py
import json
from flask import Blueprint, request, render_template, abort, jsonify, current_app

from agents.assessment_agent import AssessmentAgent
from core.md_render import render_assessment_markdown
from integrations.form_creator import create_google_form
from integrations.form_response import get_form_full_info
from utils.db import get_supabase_client
from utils.file_helper import allowed_file, save_uploaded_file

assessment_bp = Blueprint("assessments", __name__)

@assessment_bp.route("/")
def list_assessments():
    """List all assessments"""
    supabase = get_supabase_client()
    res = (
        supabase.table("assessments")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    assessments = res.data if res.data else []
    return render_template("assessments_list.html", assessments=assessments)


@assessment_bp.route("/generate", methods=["GET"])
def assessment_page():
    """Assessment generation page"""
    return render_template("assessments.html")


@assessment_bp.route("/generate", methods=["POST"])
def generate_assessment():
    """Generate assessment from uploaded PDF"""
    if "pdf" not in request.files:
        abort(400, description="Missing file field 'pdf'")

    f = request.files["pdf"]
    if (f.filename or "") == "":
        abort(400, description="No file selected")

    if not allowed_file(f.filename or ""):
        abort(400, description="Only .pdf files are allowed")

    # Save file
    upload_dir = current_app.config["UPLOAD_DIR"]
    dest = save_uploaded_file(f, upload_dir)

    # Parse options
    asmt_type = request.form.get("type", "MCQ")
    difficulty = request.form.get("difficulty", "Medium")
    try:
        count = int(request.form.get("count", "5"))
    except ValueError:
        count = 5
    rubric = request.form.get("rubric") is not None

    # Generate assessment
    agent = AssessmentAgent()
    assessment = agent.generate_assessment(
        dest.as_posix(),
        {"type": asmt_type, "difficulty": difficulty, "count": count, "rubric": rubric},
    )

    if not isinstance(assessment, dict) or "questions" not in assessment:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": assessment.get("error", "Invalid assessment result"),
                }
            ),
            400,
        )

    # Add rendered Markdown
    try:
        assessment_md = render_assessment_markdown(assessment)
        assessment_with_md = dict(assessment)
        assessment_with_md["_markdown"] = assessment_md
    except Exception:
        assessment_with_md = assessment

    return jsonify(assessment_with_md), 200


@assessment_bp.route("/api", methods=["POST"])
def save_assessment():
    """Save assessment to database"""
    try:
        supabase = get_supabase_client()
        payload = request.get_json(silent=True) or {}
        result = payload.get("result")

        if not isinstance(result, dict) or "questions" not in result:
            return (
                jsonify(
                    {"ok": False, "error": "Invalid payload: missing result.questions"}
                ),
                400,
            )

        row = {
            "original_filename": payload.get("original_filename"),
            "pdf_path": payload.get("pdf_path"),
            "options": payload.get("options"),
            "result": result,
            "google_form": payload.get("google_form"),
        }

        db_res = supabase.table("assessments").insert(row).execute()
        saved = db_res.data[0] if db_res.data else None

        return (
            jsonify({"ok": True, "id": saved["id"] if saved else None, "saved": saved}),
            200,
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@assessment_bp.route("/api", methods=["GET"])
def api_list_assessments():
    """API endpoint to list assessments"""
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table("assessments")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return jsonify(res.data or []), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@assessment_bp.route("/<uuid:assessment_id>")
def assessment_detail(assessment_id):
    """Assessment detail page"""
    supabase = get_supabase_client()
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

    title = (
        (asmt.get("result") or {}).get("title")
        or asmt.get("original_filename")
        or "Assessment"
    )
    gf = asmt.get("google_form") or {}
    form_url = gf.get("formUrl")
    form_id = gf.get("formId")

    return render_template(
        "assessment_detail.html",
        assessment=asmt,
        page_title=title,
        form_url=form_url,
        form_id=form_id,
    )


@assessment_bp.route("/api/<uuid:id>/create-form", methods=["POST"])
def create_form_for_assessment(id):
    """Create Google Form for an assessment"""
    try:
        supabase = get_supabase_client()
        sel = (
            supabase.table("assessments")
            .select("*")
            .eq("id", str(id))
            .single()
            .execute()
        )
        row = sel.data

        if not row:
            return jsonify({"ok": False, "error": "Assessment not found"}), 404

        assessment = row.get("result")
        if not isinstance(assessment, dict) or "questions" not in assessment:
            return (
                jsonify({"ok": False, "error": "Row has no valid assessment JSON"}),
                400,
            )

        title = f"Assessment - {row.get('original_filename') or 'Untitled'}"

        # Create Google Form
        form_info = create_google_form(assessment, title=title)
        if not isinstance(form_info, dict) or not form_info.get("success"):
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": form_info.get("error", "Failed to create form"),
                    }
                ),
                500,
            )

        # Update row with google_form
        upd = (
            supabase.table("assessments")
            .update({"google_form": form_info})
            .eq("id", str(id))
            .execute()
        )

        updated = upd.data[0] if upd.data else None
        return jsonify({"ok": True, "google_form": form_info, "updated": updated}), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@assessment_bp.route("/"
"<uuid:assessment_id>/responses", methods=["GET"])
def api_assessment_responses(assessment_id):
    """Fetch responses from Google Forms"""
    try:
        supabase = get_supabase_client()
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
            return (
                jsonify({"ok": False, "error": info.get("error", "Failed to fetch")}),
                500,
            )

        rows = []
        for r in info.get("responses") or []:
            rows.append(
                {
                    "email": r.get("email") or "",
                    "submitted": r.get("submitted") or "",
                    "score": r.get("totalScore"),
                    "fraction": r.get("fraction") or "",
                    "percent": r.get("percent"),
                }
            )

        return (
            jsonify(
                {
                    "ok": True,
                    "form_title": info.get("form_title"),
                    "max_points": info.get("max_points"),
                    "is_quiz": info.get("is_quiz"),
                    "num_responses": len(rows),
                    "rows": rows,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
