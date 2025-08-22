import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from urllib.parse import urlparse
from flask import Flask, jsonify
from pathlib import Path
from agents.assessment_agent import AssessmentAgent
from agents.lesson_plan_agent import LessonPlanAgent


# Ensure package imports work regardless of how the app is launched
# Compute project root based on this file's location (no reliance on CWD)
_THIS_FILE = Path(__file__).resolve()
# If this file is at repo_root/agents/assessment_agent.py, project root is two levels up
PROJECT_ROOT = _THIS_FILE.parents[1]

app = Flask(__name__)

def _is_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    try:
        u = urlparse(value)
        return u.scheme in ("http", "https")
    except Exception:
        return False
    
def _resolve_from_project_root(path_like: str) -> str:
    """
    Convert a project-root-relative path to an absolute path.
    If already absolute or a URL, return as-is.
    """
    if not isinstance(path_like, str):
        return path_like
    if _is_url(path_like):
        return path_like
    p = Path(path_like)
    if p.is_absolute():
        return str(p)
    return str((PROJECT_ROOT / p).resolve())

@app.route("/", methods=["GET"])
def index():
    asmt_agent = AssessmentAgent()
    # Prefer an env like LECTURE_SOURCE that may be URL, absolute, or project-root-relative
    source = (
        # os.environ.get("LECTURE_SOURCE")
        # or os.environ.get("LECTURE_PDF_URL")
        # or os.environ.get("LECTURE_PDF_PATH")
        # or 
        "ai-teacher-assistant/static/Lecture_Slide.pdf"  # example fallback inside the repo
    )
    # If it's a non-absolute non-URL, treat it as project-root-relative
    if isinstance(source, str) and not _is_url(source) and not Path(source).is_absolute():
        source = _resolve_from_project_root(source)
    
    assessment = asmt_agent.generate_assessment(
        source,
        {"type": "MCQ", "difficulty": "Medium", "count": 5, "rubric": True}
    )
    print(assessment)
    return jsonify(assessment)

@app.route("/lesson", methods=["GET"])
def get_lesson():
    asmt_agent = AssessmentAgent()
    # Prefer an env like LECTURE_SOURCE that may be URL, absolute, or project-root-relative
    source = (
        # os.environ.get("LECTURE_SOURCE")
        # or os.environ.get("LECTURE_PDF_URL")
        # or os.environ.get("LECTURE_PDF_PATH")
        # or 
        "ai-teacher-assistant/static/SRAS_Course_Outline.pdf"  # example fallback inside the repo
    )
    # If it's a non-absolute non-URL, treat it as project-root-relative
    if isinstance(source, str) and not _is_url(source) and not Path(source).is_absolute():
        source = _resolve_from_project_root(source)
    
    lp_agent = LessonPlanAgent()
    plan = lp_agent.generate_plan({"course_outline": os.environ.get("COURSE_OUTLINE_PATH")}, 8, 30, 1)
    print(plan)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


