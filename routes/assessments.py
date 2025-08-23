# routes/assessments.py
import json
from pathlib import Path
from flask import Blueprint, current_app, request, abort
from werkzeug.utils import secure_filename
from agents.assessment_agent import AssessmentAgent

bp = Blueprint("assessments", __name__)

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

@bp.post("/generate-assessment-test")
def generate_assessment():
    if "pdf" not in request.files:
        abort(400, description="Missing file field 'pdf'")
    f = request.files["pdf"]
    if f.filename == "":
        abort(400, description="No file selected")
    if not _allowed(f.filename):
        abort(400, description="Only .pdf files are allowed")

    dest = _save_upload(f)

    asmt_type = request.form.get("type", "MCQ")
    difficulty = request.form.get("difficulty", "Medium")
    try:
        count = int(request.form.get("count", "5"))
    except ValueError:
        count = 5
    rubric = request.form.get("rubric") is not None

    agent = AssessmentAgent()
    result = agent.generate_assessment(
        dest.as_posix(),
        {"type": asmt_type, "difficulty": difficulty, "count": count, "rubric": rubric},
    )

    return current_app.response_class(
        response=json.dumps(result, ensure_ascii=False, indent=2),
        status=200,
        mimetype="application/json",
    )
