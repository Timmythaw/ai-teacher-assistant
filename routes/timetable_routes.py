# routes/timetable_routes.py
"""
Timetable Routes with RPC User Isolation
Uses authenticated user's Google Calendar credentials
"""
from flask import Blueprint, request, jsonify, g

from agents.timetable_agent import TimetableAgent
from integrations.calendar_orchestrator import schedule_from_timetable
from utils.db import get_supabase_client, get_current_user_id
from utils.supabase_auth import login_required, require_user_owns_resource

timetable_bp = Blueprint('timetable', __name__)


@timetable_bp.route("/suggest", methods=["POST"])
@login_required  # ✅ Added: Require login
def api_timetable_suggest():
    """
    Suggest timetable slots based on lesson plan
    Uses authenticated user's Google Calendar to check availability
    """
    try:
        data = request.get_json(silent=True) or {}
        plan = data.get("plan")
        lesson_plan_id = data.get("lesson_plan_id")  # ✅ Added: Optional lesson plan ID
        
        # Validate plan JSON
        if not isinstance(plan, dict):
            return jsonify({"ok": False, "error": "Missing or invalid plan JSON"}), 400

        # ✅ Added: If lesson_plan_id provided, verify ownership
        if lesson_plan_id:
            supabase = get_supabase_client()
            try:
                # 🔥 RLS handles filtering
                check = supabase.table("lesson_plans")\
                    .select("id")\
                    .eq("id", lesson_plan_id)\
                    .single()\
                    .execute()
                
                if not check.data:
                    return jsonify({
                        "ok": False, 
                        "error": "Lesson plan not found or you don't have access"
                    }), 404
            except Exception:
                return jsonify({
                    "ok": False, 
                    "error": "Lesson plan not found or you don't have access"
                }), 404

        slot_hours = int(data.get("slot_hours") or 1)
        work_hours = data.get("work_hours") or [9, 17]
        if not (isinstance(work_hours, (list, tuple)) and len(work_hours) == 2):
            work_hours = [9, 17]
        calendar_id = (data.get("calendar_id") or "primary").strip() or "primary"
        location_hint = data.get("location_hint")

        # Generate timetable using authenticated user's calendar
        agent = TimetableAgent()
        res = agent.suggest_consistent_schedule(
            plan,
            slot_hours=slot_hours,
            work_hours=(int(work_hours[0]), int(work_hours[1])),
            calendar_id=calendar_id,
            location_hint=location_hint,
        )
        
        if not isinstance(res, dict) or res.get("error"):
            return jsonify({
                "ok": False, 
                "error": res.get("error", "Failed to suggest timetable")
            }), 500

        return jsonify({
            "ok": True,
            "suggested_slots": res.get("suggested_slots") or [],
            "metadata": res.get("metadata") or {},
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@timetable_bp.route("/schedule", methods=["POST"])
@login_required  # ✅ Added: Require login
def api_timetable_schedule():
    """
    Schedule timetable to user's Google Calendar
    Creates events in authenticated user's calendar
    """
    try:
        data = request.get_json(silent=True) or {}
        tt = data.get("timetable")
        lesson_plan_id = data.get("lesson_plan_id")  # ✅ Added: Optional lesson plan ID
        
        if not isinstance(tt, dict) or "suggested_slots" not in tt:
            return jsonify({
                "ok": False, 
                "error": "Missing timetable.suggested_slots"
            }), 400

        # ✅ Added: If lesson_plan_id provided, verify ownership
        if lesson_plan_id:
            supabase = get_supabase_client()
            try:
                # 🔥 RLS handles filtering
                check = supabase.table("lesson_plans")\
                    .select("id")\
                    .eq("id", lesson_plan_id)\
                    .single()\
                    .execute()
                
                if not check.data:
                    return jsonify({
                        "ok": False, 
                        "error": "Lesson plan not found or you don't have access"
                    }), 404
            except Exception:
                return jsonify({
                    "ok": False, 
                    "error": "Lesson plan not found or you don't have access"
                }), 404

        # Schedule to user's calendar
        results = schedule_from_timetable(tt)
        
        if not isinstance(results, list):
            return jsonify({"ok": False, "error": "Scheduling failed"}), 500

        # Calculate summary
        total = len(results)
        ok_count = sum(1 for r in results if r.get("ok"))
        failed = total - ok_count
        
        # Find first successful event link
        first_link = None
        for r in results:
            link = r.get("html_link") or r.get("htmlLink")
            if r.get("ok") and link:
                first_link = link
                break

        return jsonify({
            "ok": True,
            "results": results,
            "summary": {
                "total": total, 
                "inserted": ok_count, 
                "failed": failed
            },
            "first_link": first_link,
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@timetable_bp.route("/api/for-lesson-plan/<uuid:lesson_plan_id>", methods=["POST"])
@login_required  # ✅ Added: Require login
@require_user_owns_resource('lesson_plans', 'lesson_plan_id')  # ✅ Added: Verify ownership
def api_generate_timetable_for_lesson_plan(lesson_plan_id):
    """
    Generate and schedule timetable for a specific lesson plan
    Combines suggest + schedule in one endpoint
    Only if user owns the lesson plan
    """
    try:
        supabase = get_supabase_client()
        
        # Get lesson plan - 🔥 RLS + decorator handle filtering
        sel = supabase.table("lesson_plans")\
            .select("result")\
            .eq("id", str(lesson_plan_id))\
            .single()\
            .execute()
        
        lesson_plan = sel.data
        if not lesson_plan:
            return jsonify({"ok": False, "error": "Lesson plan not found"}), 404
        
        plan = lesson_plan.get("result")
        if not isinstance(plan, dict):
            return jsonify({"ok": False, "error": "Invalid lesson plan data"}), 400

        # Get parameters from request
        data = request.get_json(silent=True) or {}
        slot_hours = int(data.get("slot_hours") or 1)
        work_hours = data.get("work_hours") or [9, 17]
        calendar_id = (data.get("calendar_id") or "primary").strip() or "primary"
        location_hint = data.get("location_hint")
        auto_schedule = data.get("auto_schedule", False)  # Whether to schedule immediately

        # Suggest timetable
        agent = TimetableAgent()
        res = agent.suggest_consistent_schedule(
            plan,
            slot_hours=slot_hours,
            work_hours=(int(work_hours[0]), int(work_hours[1])),
            calendar_id=calendar_id,
            location_hint=location_hint,
        )
        
        if not isinstance(res, dict) or res.get("error"):
            return jsonify({
                "ok": False, 
                "error": res.get("error", "Failed to suggest timetable")
            }), 500

        # Optionally schedule immediately
        schedule_results = None
        if auto_schedule:
            schedule_results = schedule_from_timetable(res)
            total = len(schedule_results) if isinstance(schedule_results, list) else 0
            ok_count = sum(1 for r in schedule_results if r.get("ok")) if schedule_results else 0

        return jsonify({
            "ok": True,
            "suggested_slots": res.get("suggested_slots") or [],
            "metadata": res.get("metadata") or {},
            "scheduled": auto_schedule,
            "schedule_summary": {
                "total": total,
                "inserted": ok_count,
                "failed": total - ok_count
            } if auto_schedule else None,
        }), 200
        
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
