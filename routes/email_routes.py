# routes/email_routes.py
"""
Email Routes with RPC User Isolation
Database automatically filters data via RLS
"""
from flask import Blueprint, request, render_template, jsonify, g

from agents.email_agent import EmailAgent
from utils.db import get_supabase_client
from utils.supabase_auth import login_required, require_user_owns_resource

email_bp = Blueprint("email", __name__)


@email_bp.route("/", methods=["GET"])
@login_required  # ✅ Added: Require login
def email_page():
    """Email compose page"""
    return render_template("email.html", user=g.current_user)


@email_bp.route("/compose", methods=["POST"])
@login_required  # ✅ Added: Require login
def email_compose():
    """
    Compose and send/draft email to single recipient
    Uses authenticated user's Google credentials
    """
    to_email = (request.form.get("to_email") or "").strip()
    subject = request.form.get("subject") or ""
    notes = request.form.get("notes") or ""
    tone = request.form.get("tone") or "professional, friendly"
    action = (request.form.get("action") or "send").strip().lower()
    cc = (request.form.get("cc") or "").strip()
    bcc = (request.form.get("bcc") or "").strip()

    # Build prompt for EmailAgent
    prompt = f"""to: {to_email}
subject: {subject}
tone: {tone}
action: {action}
cc: {cc}
bcc: {bcc}
notes: {notes}
"""

    try:
        agent = EmailAgent()
        result = agent.run(prompt, default_use_html=True)
        status = 200 if result.get("ok") else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@email_bp.route("/api/send-batch", methods=["POST"])
@login_required  # ✅ Added: Require login
def api_email_send_batch():
    """
    Send email to all students in a batch
    Only if user owns the batch
    """
    try:
        supabase = get_supabase_client()
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

        # ✅ Added: Verify user owns the batch before proceeding
        try:
            batch_check = supabase.table("batches")\
                .select("id")\
                .eq("id", batch_id)\
                .single()\
                .execute()
            
            if not batch_check.data:
                return jsonify({
                    "ok": False, 
                    "error": "Batch not found or you don't have access"
                }), 404
        except Exception:
            return jsonify({
                "ok": False, 
                "error": "Batch not found or you don't have access"
            }), 404

        # If assessment_id is provided, fetch Google Form URL
        form_url = None
        if assessment_id:
            try:
                # 🔥 RLS handles filtering - only returns if user owns assessment
                sel = (
                    supabase.table("assessments")
                    .select("google_form")
                    .eq("id", assessment_id)
                    .single()
                    .execute()
                )
                gf = (sel.data or {}).get("google_form") if sel and sel.data else None
                if isinstance(gf, dict):
                    form_url = gf.get("formUrl")
            except Exception:
                form_url = None

        # Append form link to notes if available
        if form_url:
            notes = (notes.strip() + "\n\nGoogle Form: " + form_url).strip()

        # Fetch students - 🔥 RLS handles filtering (students belong to user's batch)
        stu_res = (
            supabase.table("students")
            .select("student_id,name,email")
            .eq("batch_id", batch_id)
            .execute()
        )
        students = stu_res.data or []

        if not students:
            return (
                jsonify({"ok": False, "error": "No students found for this batch"}),
                404,
            )

        agent = EmailAgent()
        results, sent, drafted, failed = [], 0, 0, 0

        for s in students:
            student_id = s.get("student_id")
            name = (s.get("name") or "").strip()
            email = (s.get("email") or "").strip()
            
            if not email:
                results.append(
                    {
                        "ok": False, 
                        "student_id": student_id, 
                        "name": name,
                        "error": "Missing email"
                    }
                )
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
                results.append(
                    {
                        "ok": ok,
                        "student_id": student_id,
                        "name": name,
                        "to": email,
                        "mode": r.get("mode"),
                        "error": r.get("error"),
                    }
                )
                if ok and r.get("mode") == "send":
                    sent += 1
                elif ok and r.get("mode") == "draft":
                    drafted += 1
                else:
                    failed += 1
            except Exception as e:
                results.append(
                    {
                        "ok": False,
                        "student_id": student_id,
                        "name": name,
                        "to": email,
                        "error": str(e),
                    }
                )
                failed += 1

        return (
            jsonify(
                {
                    "ok": True,
                    "summary": {
                        "total": len(students),
                        "sent": sent,
                        "drafted": drafted,
                        "failed": failed,
                    },
                    "results": results,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@email_bp.route("/api/batches", methods=["GET"])
@login_required  # ✅ Added: Require login
def api_list_batches_for_email():
    """
    API: Get list of user's batches for email dropdown
    RLS automatically filters by user_id
    """
    try:
        supabase = get_supabase_client()
        
        # 🔥 RLS handles filtering
        res = supabase.table("batches")\
            .select("id, name, students(count)")\
            .order("name")\
            .execute()
        
        batches = []
        for row in (res.data or []):
            cnt = 0
            s = row.get("students")
            if isinstance(s, list) and s:
                cnt = s[0].get("count", 0)
            elif isinstance(s, dict):
                cnt = s.get("count", 0)
            
            batches.append({
                "id": row["id"],
                "name": row.get("name", "Untitled"),
                "student_count": cnt
            })
        
        return jsonify({"ok": True, "batches": batches}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@email_bp.route("/api/assessments", methods=["GET"])
@login_required  # ✅ Added: Require login
def api_list_assessments_for_email():
    """
    API: Get list of user's assessments with Google Forms for email dropdown
    RLS automatically filters by user_id
    """
    try:
        supabase = get_supabase_client()
        
        # 🔥 RLS handles filtering - only get assessments with Google Forms
        res = supabase.table("assessments")\
            .select("id, original_filename, google_form")\
            .not_.is_("google_form", "null")\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
        
        assessments = []
        for row in (res.data or []):
            gf = row.get("google_form")
            if isinstance(gf, dict) and gf.get("formUrl"):
                assessments.append({
                    "id": row["id"],
                    "title": row.get("original_filename", "Untitled"),
                    "form_url": gf.get("formUrl")
                })
        
        return jsonify({"ok": True, "assessments": assessments}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
