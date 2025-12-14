# routes/batch_routes.py
import io
import csv
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify

from utils.db import get_supabase_client

batch_bp = Blueprint('batches', __name__)

@batch_bp.route("/")
def batches_page():
    """List all batches"""
    supabase = get_supabase_client()
    response = supabase.table('batches') \
        .select('id, name, students(count)') \
        .execute()

    batches = response.data if response.data else []
    return render_template('course_batches.html', batches=batches)

@batch_bp.route("/<string:batch_id>")
def batch_show(batch_id):
    """Show students in a specific batch"""
    supabase = get_supabase_client()
    
    # Get batch info
    bres = supabase.table("batches") \
        .select("id,name") \
        .eq("id", batch_id) \
        .single() \
        .execute()
    batch = bres.data
    if not batch:
        return render_template("404.html"), 404

    # Get students in batch
    sres =(
         supabase.table("students") 
        .select("student_id,name,email") 
        .eq("batch_id", batch_id) 
        .order("name") 
        .execute()
    )
    students = sres.data or []

    return render_template("batch_students.html", batch=batch, students=students)

@batch_bp.route("/add-new-batch", methods=["POST"])
def create_batch_upload_csv():
    """Create new batch and upload students from CSV"""
    supabase = get_supabase_client()
    batch_name = request.form.get("batch_name")
    file = request.files.get("students_csv")

    if not batch_name or not file:
        flash("Batch name and CSV file are required.", "error")
        return redirect(url_for("batches.batches_page"))

    # Read CSV content
    stream = io.StringIO(file.stream.read().decode("utf-8"))
    csv_reader = csv.DictReader(stream)

    # Insert batch into Supabase
    batch_resp = supabase.table("batches").insert({"name": batch_name}).execute()
    batch_id = batch_resp.data[0]["id"] if batch_resp.data else None
    
    if not batch_id:
        flash("Failed to create batch", "error")
        return redirect(url_for("batches.batches_page"))

    # Prepare students to insert
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
        supabase.table("students").insert(students_to_insert).execute()

    return redirect(url_for("batches.batches_page"))

@batch_bp.route("/api", methods=["GET"])
def api_list_batches():
    """API: List all batches with student count"""
    try:
        supabase = get_supabase_client()
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
def api_list_students(id):
    """API: List students in a batch"""
    try:
        supabase = get_supabase_client()
        res = supabase.table("students") \
            .select("name,email") \
            .eq("batch_id", id) \
            .order("name", desc=False) \
            .execute()
        return jsonify({"ok": True, "students": res.data or []}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
