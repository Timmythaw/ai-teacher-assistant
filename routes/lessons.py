# routes/lessons.py
import json
from pathlib import Path
from flask import Blueprint, current_app, request, abort
from werkzeug.utils import secure_filename
from agents.lesson_plan_agent import LessonPlanAgent

bp = Blueprint("lessons", __name__)

def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in current_app.config["ALLOWED_EXTENSIONS"]

def _save_upload(fs) -> Path:
    upload_dir: Path = current_app.config["UPLOAD_DIR"]
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = secure_filename(fs.filename)
    dest = upload_dir / name
    i = 1
    while dest.exists():
        dest = upload_dir / f"{dest.stem}_{i}{dest.suffix}"
        i += 1
    fs.save(dest.as_posix())
    return dest

@bp.post("/generate-lesson-plan")
def generate_lesson_plan():
    if "pdf" not in request.files:
        abort(400, description="Missing file field 'pdf'")
    f = request.files["pdf"]
    if f.filename == "":
        abort(400, description="No file selected")
    if not _allowed(f.filename):
        abort(400, description="Only .pdf files are allowed")

    dest = _save_upload(f)

    weeks = 0
    num_stu = 0
    section_per_week = 0

    lp_agent = LessonPlanAgent()
    plan = lp_agent.generate_plan({"course_outline": dest.as_posix()}, weeks, num_stu, section_per_week)

    return current_app.response_class(
        response=json.dumps(plan, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json",
    )
