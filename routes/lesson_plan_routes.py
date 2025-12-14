# routes/lesson_plan_routes.py
import json
from flask import Blueprint, request, render_template, abort, jsonify, current_app

from agents.lesson_plan_agent import LessonPlanAgent
from core.md_render import render_lesson_plan_markdown
from utils.db import get_supabase_client
from utils.file_helper import allowed_file, save_uploaded_file

lesson_plan_bp = Blueprint("lesson_plans", __name__)


@lesson_plan_bp.route("/")
def list_lesson_plans():
    """List all lesson plans"""
    try:
        supabase = get_supabase_client()
        res = (
            supabase.table("lesson_plans")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        lesson_plans = res.data or []
        return render_template("lesson_plans_list.html", lesson_plans=lesson_plans)
    except Exception as e:
        return (
            render_template("lesson_plans_list.html", lesson_plans=[], error=str(e)),
            200,
        )


@lesson_plan_bp.route("/generator", methods=["GET"])
def lesson_generator_page():
    """Lesson plan generator page"""
    return render_template("lesson_generator.html")


@lesson_plan_bp.route("/generate", methods=["POST"])
def generate_lesson_plan():
    """Generate lesson plan from course outline"""
    if "course_outline" not in request.files:
        abort(400, description="Missing file field 'course_outline'")

    f = request.files["course_outline"]
    if (f.filename or "") == "":
        abort(400, description="No file selected")

    if not allowed_file(f.filename or ""):
        abort(400, description="Only .pdf files are allowed")

    # Save file
    upload_dir = current_app.config["UPLOAD_DIR"]
    dest = save_uploaded_file(f, upload_dir)

    # Parse options
    data = request.form or request.get_json(silent=True) or {}

    def _int_param(name, default):
        raw = data.get(name)
        try:
            return int(raw) if raw not in (None, "") else default
        except ValueError:
            return default

    weeks = _int_param("weeks", 8)
    num_stu = _int_param("students", 20)
    section_per_week = _int_param("sections", 1)

    # Generate lesson plan
    lp_agent = LessonPlanAgent()
    plan = lp_agent.generate_plan(
        {"course_outline": dest.as_posix()}, weeks, num_stu, section_per_week
    )

    # Attach rendered markdown
    try:
        plan_md = (
            render_lesson_plan_markdown(plan)
            if isinstance(plan, dict) and not plan.get("error")
            else None
        )
        plan_with_md = dict(plan)
        if plan_md is not None:
            plan_with_md["_markdown"] = plan_md
    except Exception:
        plan_with_md = plan

    return jsonify(plan_with_md), 200


@lesson_plan_bp.route("/api", methods=["POST"])
def save_lesson_plan():
    """Save lesson plan to database"""
    try:
        supabase = get_supabase_client()
        payload = request.get_json(silent=True) or {}
        result = payload.get("result")

        if not isinstance(result, dict):
            return (
                jsonify(
                    {"ok": False, "error": "Invalid payload: missing result object"}
                ),
                400,
            )

        row = {
            "original_filename": payload.get("original_filename"),
            "pdf_path": payload.get("pdf_path"),
            "options": payload.get("options"),
            "result": result,
        }

        db_res = supabase.table("lesson_plans").insert(row).execute()
        saved = (db_res.data or [None])[0]

        return (
            jsonify({"ok": True, "id": saved["id"] if saved else None, "saved": saved}),
            200,
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@lesson_plan_bp.route("/api/<uuid:id>/markdown", methods=["GET"])
def lesson_plan_markdown(id):
    """Get lesson plan as markdown"""
    try:
        supabase = get_supabase_client()
        sel = (
            supabase.table("lesson_plans")
            .select("result")
            .eq("id", str(id))
            .single()
            .execute()
        )
        row = sel.data or {}
        result = row.get("result")

        if not isinstance(result, dict):
            return (
                jsonify(
                    {"ok": False, "error": "Lesson plan not found or invalid JSON"}
                ),
                404,
            )

        md = render_lesson_plan_markdown(result)
        return jsonify({"ok": True, "markdown": md}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
