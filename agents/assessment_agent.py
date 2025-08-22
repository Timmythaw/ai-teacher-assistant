import sys
import os
import json
from urllib.parse import urlparse
from pathlib import Path

# Ensure package imports work regardless of how the app is launched
# Compute project root based on this file's location (no reliance on CWD)
_THIS_FILE = Path(__file__).resolve()
# If this file is at repo_root/agents/assessment_agent.py, project root is two levels up
PROJECT_ROOT = _THIS_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from core.ai_client import chat_completion
from core.pdf_tool import extract_text_from_pdf
from core.logger import logger


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


class AssessmentAgent:
    def __init__(self, model="openai/gpt-5-chat-latest"):
        self.model = model

    def _material_to_text(self, course_material: str) -> str:
        """
        Accepts:
        - URL to a PDF
        - Absolute path to a PDF
        - Project-root-relative path to a PDF
        - Raw text
        """
        if not isinstance(course_material, str) or not course_material.strip():
            return ""

        # If it looks like a URL or a path to a PDF, route to PDF extractor
        if _is_url(course_material) or course_material.lower().endswith(".pdf"):
            locator = course_material
            # If not URL and not absolute, treat as project-root-relative
            if not _is_url(locator) and not Path(locator).is_absolute():
                locator = _resolve_from_project_root(locator)
            return extract_text_from_pdf(locator)

        # Heuristic: if it exists on disk (even without .pdf), treat as a file path
        maybe_path = Path(course_material)
        if not _is_url(course_material) and maybe_path.exists():
            locator = course_material if maybe_path.is_absolute() else _resolve_from_project_root(course_material)
            # If it turns out to be a PDF, extract; otherwise read as text
            if str(locator).lower().endswith(".pdf"):
                return extract_text_from_pdf(locator)
            try:
                return Path(locator).read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning("Failed to read text file %s: %s", locator, e)

        # Otherwise treat as raw text
        return course_material

    def generate_assessment(self, course_material: str, options: dict) -> dict:
        try:
            print(course_material)
            logger.info("AssessmentAgent started with inputs: %s", options)

            material_text = self._material_to_text(course_material)
            print(material_text)
            logger.info("Material text length: %d", len(material_text))

            if not material_text.strip():
                logger.warning("No valid course material found in %s", course_material)
                return {"error": "No valid course material found."}

            system_prompt = """
            You are an assessment designer.
            Create an assessment based on provided material.
            JSON structure should include:
            - type (MCQ, ShortAnswer, Project)
            - difficulty
            - questions: [{q, options(if MCQ), answer}]
            - rubric: [{criteria, points}] (if rubric requested)
            RESPOND IN CORRECT JSON FORMAT ONLY.
            """

            user_prompt = f"""
            Create a {options.get('type', 'MCQ')} assessment.
            Difficulty: {options.get('difficulty', 'Medium')}.
            Number of questions: {options.get('count', 5)}.
            Include rubric: {options.get('rubric', True)}.
            """

            raw = chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": material_text},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4
            )
            print(raw)
            try:
                result = json.loads(raw)
                logger.info(
                    "AssessmentAgent successfully generated assessment with %d questions",
                    len(result.get("questions", []))
                )
                return result

            except json.JSONDecodeError:
                logger.error("Model did not return valid JSON. Raw output: %s", raw)
                return {"error": "Model did not return valid JSON."}

        except Exception as e:
            logger.error("AssessmentAgent failed: %s", e, exc_info=True)
            return {"error": f"AssessmentAgent failed: {e}"}


# Example direct invocation:
# - Supports project-root-relative paths like "assets/lectures/week1.pdf"
# - Absolute paths
# - URLs (if your extractor supports downloading)
if __name__ == "__main__":
    asmt_agent = AssessmentAgent()
    # Prefer an env like LECTURE_SOURCE that may be URL, absolute, or project-root-relative
    source = (
        # os.environ.get("LECTURE_SOURCE")
        # or os.environ.get("LECTURE_PDF_URL")
        # or os.environ.get("LECTURE_PDF_PATH")
        # or 
        "static/Lecture_Slide.pdf"  # example fallback inside the repo
    )
    # If it's a non-absolute non-URL, treat it as project-root-relative
    if isinstance(source, str) and not _is_url(source) and not Path(source).is_absolute():
        source = _resolve_from_project_root(source)

    assessment = asmt_agent.generate_assessment(
        source,
        {"type": "MCQ", "difficulty": "Medium", "count": 5, "rubric": True}
    )
    print(source)
    print(assessment)
