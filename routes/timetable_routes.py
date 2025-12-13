# routes/timetable_routes.py
from flask import Blueprint, request, jsonify

from agents.timetable_agent import TimetableAgent
from integrations.calendar_orchestrator import schedule_from_timetable

timetable_bp = Blueprint('timetable', __name__)

@timetable_bp.route("/suggest", methods=["POST"])
def api_timetable_suggest():
    """Suggest timetable slots based on lesson plan"""
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

@timetable_bp.route("/schedule", methods=["POST"])
def api_timetable_schedule():
    """Schedule timetable to Google Calendar"""
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
