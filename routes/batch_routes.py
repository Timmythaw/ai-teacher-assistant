# routes/batch_routes.py
"""
Batch Routes with RPC User Isolation
Database automatically filters data via RLS
"""
import io
import csv
import json
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, g

from utils.db import get_supabase_client, get_current_user_id
from utils.supabase_auth import login_required, require_user_owns_resource

batch_bp = Blueprint('batches', __name__)


@batch_bp.route("/")
@login_required  # ✅ Added: Require login
def batches_page():
    """
    List current user's batches
    RLS automatically filters by user_id
    """
    supabase = get_supabase_client()
    
    # 🔥 RLS handles filtering - no .eq('user_id') needed!
    response = supabase.table('batches') \
        .select('id, name, students(count)') \
        .execute()

    batches = response.data if response.data else []
    
    # ✅ Added: Pass user to template
    return render_template('course_batches.html', batches=batches, user=g.current_user)


@batch_bp.route("/<string:batch_id>")
@login_required  # ✅ Added: Require login
@require_user_owns_resource('batches', 'batch_id')  # ✅ Added: Verify ownership
def batch_show(batch_id):
    """
    Show students in a specific batch
    Only if user owns the batch
    """
    supabase = get_supabase_client()
    
    # Get batch info - 🔥 RLS handles filtering
    bres = supabase.table("batches") \
        .select("id,name") \
        .eq("id", batch_id) \
        .single() \
        .execute()
    batch = bres.data
    
    if not batch:
        return render_template("404.html"), 404

    # Get students in batch - 🔥 RLS handles filtering
    sres = (
        supabase.table("students") 
        .select("student_id,name,email") 
        .eq("batch_id", batch_id) 
        .order("name") 
        .execute()
    )
    students = sres.data or []

    # ✅ Added: Pass user to template
    return render_template("batch_students.html", batch=batch, students=students, user=g.current_user)


@batch_bp.route("/add-new-batch", methods=["POST"])
@login_required  # ✅ Added: Require login
def create_batch_upload_csv():
    """
    Create new batch and upload students from CSV
    Automatically sets user_id for ownership
    """
    user_id = get_current_user_id()  # ✅ Added: Get current user
    supabase = get_supabase_client()
    batch_name = request.form.get("batch_name")
    file = request.files.get("students_csv")
    students_manual_raw = None

    # Accept manual students from form-encoded multipart/form-data
    if request.form and request.form.get("students_manual"):
        students_manual_raw = request.form.get("students_manual")

    # Accept JSON payload when client posts application/json
    if request.is_json:
        try:
            j = request.get_json(silent=True) or {}
            # payload might include students_manual as array or JSON string
            if isinstance(j.get("students_manual"), str):
                students_manual_raw = j.get("students_manual")
            elif isinstance(j.get("students_manual"), list):
                # convert list back to JSON string for unified parsing below
                students_manual_raw = json.dumps(j.get("students_manual"))
            # ensure batch_name from JSON is used if form field missing
            if not batch_name and j.get("batch_name"):
                batch_name = j.get("batch_name")
        except Exception:
            pass

    if not batch_name or (not file and not students_manual_raw):
        flash("Batch name and either a CSV file or manual students are required.", "error")
        return redirect(url_for("batches.batches_page"))

    # If CSV is provided, prepare a csv reader
    csv_reader = None
    if file:
        try:
            stream = io.StringIO(file.stream.read().decode("utf-8"))
            csv_reader = csv.DictReader(stream)
        except Exception:
            csv_reader = None

    # Insert batch into Supabase with user_id
    batch_resp = supabase.table("batches").insert({
        "name": batch_name,
        "user_id": user_id  # ✅ Added: Set ownership
    }).execute()
    
    batch_id = batch_resp.data[0]["id"] if batch_resp.data else None
    
    if not batch_id:
        flash("Failed to create batch", "error")
        return redirect(url_for("batches.batches_page"))

    # Prepare students to insert from CSV and/or manual JSON
    students_to_insert = []

    if csv_reader:
        for row in csv_reader:
            name = (row.get("name") or "").strip()
            email = (row.get("email") or "").strip()
            if not name or not email:
                continue
            students_to_insert.append({
                "batch_id": batch_id,
                "name": name,
                "email": email,
                "user_id": user_id
            })

    # If manual students JSON provided, parse and add
    if students_manual_raw:
        try:
            manual_list = json.loads(students_manual_raw)
            if isinstance(manual_list, list):
                for entry in manual_list:
                    name = (entry.get("name") or "").strip()
                    email = (entry.get("email") or "").strip()
                    if not name or not email:
                        continue
                    students_to_insert.append({
                        "batch_id": batch_id,
                        "name": name,
                        "email": email,
                        "user_id": user_id
                    })
        except Exception:
            # ignore malformed JSON and continue (or you could flash an error)
            pass

    # Insert students if any
    if students_to_insert:
        supabase.table("students").insert(students_to_insert).execute()

    flash(f"Batch '{batch_name}' created with {len(students_to_insert)} students!", "success")
    return redirect(url_for("batches.batches_page"))


@batch_bp.route("/api", methods=["GET"])
@login_required  # ✅ Added: Require login
def api_list_batches():
    """
    API: List current user's batches with student count
    RLS automatically filters by user_id
    """
    try:
        supabase = get_supabase_client()
        
        # 🔥 RLS handles filtering - no .eq('user_id') needed!
        res = supabase.table("batches") \
            .select("id,name,students(count)") \
            .order("name", desc=False) \
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
                "name": row.get("name") or "Untitled", 
                "student_count": cnt
            })
        return jsonify({"ok": True, "batches": batches}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@batch_bp.route("/api/<id>/students", methods=["GET"])
@login_required  # ✅ Added: Require login
@require_user_owns_resource('batches', 'id')  # ✅ Added: Verify batch ownership
def api_list_students(id):
    """
    API: List students in a batch
    Only if user owns the batch
    """
    try:
        supabase = get_supabase_client()
        
        # 🔥 RLS handles filtering - students belong to user
        res = supabase.table("students") \
            .select("student_id,name,email") \
            .eq("batch_id", id) \
            .order("name", desc=False) \
            .execute()
        
        return jsonify({"ok": True, "students": res.data or []}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@batch_bp.route("/api/<string:batch_id>", methods=["DELETE"])
@login_required  # ✅ Added: Require login
@require_user_owns_resource('batches', 'batch_id')  # ✅ Added: Verify ownership
def api_delete_batch(batch_id):
    """
    API: Delete a batch
    Only if user owns the batch
    Students will be cascade deleted (if FK is set up properly)
    """
    try:
        supabase = get_supabase_client()

        # First delete students in the batch to ensure cleanup (RLS applies)
        try:
            supabase.table("students").delete().eq("batch_id", batch_id).execute()
        except Exception:
            # ignore and continue to attempt batch delete - we'll report any error below
            pass

        # Then delete the batch itself
        res = supabase.table("batches").delete().eq("id", batch_id).execute()

        return jsonify({"ok": True, "message": "Batch and its students deleted successfully"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
