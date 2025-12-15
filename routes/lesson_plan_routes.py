# routes/lesson_plan_routes.py
"""
Lesson Plan Routes with RPC User Isolation
Database automatically filters data via RLS
"""
import json
from flask import Blueprint, request, render_template, abort, jsonify, current_app, g

from agents.lesson_plan_agent import LessonPlanAgent
from core.md_render import render_lesson_plan_markdown
from utils.db import get_supabase_client, get_current_user_id
from utils.file_helper import allowed_file, save_uploaded_file
from utils.supabase_auth import login_required, require_user_owns_resource

lesson_plan_bp = Blueprint("lesson_plans", __name__)


@lesson_plan_bp.route("/")
@login_required  # ✅ Added: Require login
def list_lesson_plans():
    """
    List current user's lesson plans
    RLS automatically filters by user_id
    """
    try:
        supabase = get_supabase_client()
        
        # 🔥 RLS handles filtering - no .eq('user_id') needed!
        res = (
            supabase.table("lesson_plans")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        lesson_plans = res.data or []
        
        # ✅ Added: Pass user to template
        return render_template("lesson_plans_list.html", lesson_plans=lesson_plans, user=g.current_user)
    except Exception as e:
        return (
            render_template("lesson_plans_list.html", lesson_plans=[], error=str(e), user=g.current_user),
            200,
        )


@lesson_plan_bp.route("/generator", methods=["GET"])
@login_required  # ✅ Added: Require login
def lesson_generator_page():
    """Lesson plan generator page"""
    return render_template("lesson_generator.html", user=g.current_user)


@lesson_plan_bp.route("/generate", methods=["POST"])
@login_required  # ✅ Added: Require login
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
@login_required  # ✅ Added: Require login
def save_lesson_plan():
    """
    Save lesson plan to database with user ownership
    Sets user_id automatically
    """
    try:
        user_id = get_current_user_id()  # ✅ Added: Get current user
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
            "user_id": user_id,  # ✅ Added: Set ownership
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


@lesson_plan_bp.route("/api", methods=["GET"])
@login_required  # ✅ Added: Require login
def api_list_lesson_plans():
    """
    API endpoint to list current user's lesson plans
    RLS automatically filters by user_id
    """
    try:
        supabase = get_supabase_client()
        
        # 🔥 RLS handles filtering
        res = (
            supabase.table("lesson_plans")
            .select("*")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return jsonify({"ok": True, "lesson_plans": res.data or []}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@lesson_plan_bp.route("/<uuid:lesson_plan_id>")
@login_required  # ✅ Added: Require login
@require_user_owns_resource('lesson_plans', 'lesson_plan_id')  # ✅ Added: Verify ownership
def lesson_plan_detail(lesson_plan_id):
    """
    Lesson plan detail page
    Only if user owns the lesson plan
    """
    supabase = get_supabase_client()
    
    # 🔥 RLS + decorator handle filtering
    sel = (
        supabase.table("lesson_plans")
        .select("*")
        .eq("id", str(lesson_plan_id))
        .single()
        .execute()
    )
    lesson_plan = sel.data
    
    if not lesson_plan:
        return render_template("404.html"), 404

    title = (
        lesson_plan.get("original_filename") or 
        (lesson_plan.get("result") or {}).get("course_title") or 
        "Lesson Plan"
    )

    # Render markdown if result exists
    try:
        result = lesson_plan.get("result")
        if isinstance(result, dict):
            markdown = render_lesson_plan_markdown(result)
        else:
            markdown = None
    except Exception:
        markdown = None

    return render_template(
        "lesson_plan_detail.html",
        lesson_plan=lesson_plan,
        page_title=title,
        markdown=markdown,
        user=g.current_user
    )


@lesson_plan_bp.route("/api/<uuid:id>/markdown", methods=["GET"])
@login_required  # ✅ Added: Require login
@require_user_owns_resource('lesson_plans', 'id')  # ✅ Added: Verify ownership
def lesson_plan_markdown(id):
    """
    Get lesson plan as markdown
    Only if user owns the lesson plan
    """
    try:
        supabase = get_supabase_client()
        
        # 🔥 RLS + decorator handle filtering
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


@lesson_plan_bp.route("/api/<uuid:id>", methods=["DELETE"])
@login_required  # ✅ Added: Require login
@require_user_owns_resource('lesson_plans', 'id')  # ✅ Added: Verify ownership
def api_delete_lesson_plan(id):
    """
    Delete a lesson plan
    Only if user owns it
    """
    try:
        supabase = get_supabase_client()
        
        # 🔥 RLS handles filtering
        res = supabase.table("lesson_plans")\
            .delete()\
            .eq("id", str(id))\
            .execute()
        
        return jsonify({"ok": True, "message": "Lesson plan deleted successfully"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
