import os
from typing import Dict, Any, Optional, List
from core.logger import logger
from core.google_client import get_google_service
from integrations.forms_fetch import fetch_form_structure, fetch_all_responses
from integrations.form_utils import extract_form_id


def _extract_answer_value(ans_obj: Dict[str, Any]) -> str:
    """Join text/choice answers (Google Forms API shape) into a single string."""
    if not isinstance(ans_obj, dict):
        return ""
    if "textAnswers" in ans_obj and ans_obj.get("textAnswers", {}).get("answers"):
        return "; ".join(
            a.get("value", "")
            for a in ans_obj["textAnswers"].get("answers", [])
            if a.get("value")
        )
    if "choiceAnswers" in ans_obj and ans_obj.get("choiceAnswers", {}).get("answers"):
        return "; ".join(
            a.get("value", "")
            for a in ans_obj["choiceAnswers"].get("answers", [])
            if a.get("value")
        )
    return ""


def _safe_float(x) -> Optional[float]:
    """Try to coerce score-like values to float; return None on failure."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).strip())
    except Exception:
        return None


def get_form_full_info(link_or_id: str) -> Dict[str, Any]:
    """
    Fetch form structure and responses, returning all relevant info:
    - form_title
    - is_quiz
    - max_points (sum of question pointValue if quiz)
    - questions: [{itemId, title, type, pointValue}]
    - responses: [{
        submitted,
        answers: {itemId: value},
        email,
        totalScore,       # numeric if quiz+graded
        fraction,         # "3/6" when both totalScore and max_points are known
        percent           # numeric 0..100 (float) when both known
    }]
    Fallbacks:
      - email falls back to the first item whose title contains "email"
      - score falls back to the first item whose title contains "mark"/"score"
    """
    try:
        form_id = extract_form_id(link_or_id)
        if not form_id:
            return {"ok": False, "error": "Invalid form link or ID"}

        service = get_google_service("forms", "v1")
        form = fetch_form_structure(service, form_id)
        responses = fetch_all_responses(service, form_id)

        # Is this a quiz?
        settings = (form or {}).get("settings", {}) or {}
        quiz_settings = settings.get("quizSettings", {}) or {}
        is_quiz = bool(quiz_settings.get("isQuiz"))

        # Build questions list + compute max_points
        questions: List[Dict[str, Any]] = []
        max_points = 0.0
        email_item_id = None
        score_item_id = None

        for item in (form.get("items") or []):
            item_id = item.get("itemId")
            title = item.get("title", "Untitled Question")
            qtype = "Unknown"
            point_value = 0.0

            q = (item.get("questionItem") or {}).get("question", {}) or {}
            if "textQuestion" in q:
                qtype = "Short Answer"
            elif "choiceQuestion" in q:
                qtype = "Multiple Choice"
            elif "paragraphQuestion" in q:
                qtype = "Paragraph"

            # Quiz points (if quiz; non-quiz forms typically omit grading)
            grading = q.get("grading", {}) or {}
            pv = grading.get("pointValue")
            if isinstance(pv, (int, float)):
                point_value = float(pv)
                max_points += point_value

            # Map likely email/score items by title as fallbacks
            lt = title.lower()
            if email_item_id is None and "email" in lt:
                email_item_id = item_id
            if score_item_id is None and ("mark" in lt or "score" in lt):
                score_item_id = item_id

            questions.append({
                "itemId": item_id,
                "title": title,
                "type": qtype,
                "pointValue": point_value
            })

        # Extract responses, compute totalScore/fraction/percent
        structured_responses = []
        for resp in (responses or []):
            answers = resp.get("answers", {}) or {}

            # Prefer authoritative fields
            email = resp.get("respondentEmail") or ""
            total_score = _safe_float(resp.get("totalScore"))  # None if not quiz/graded

            # Fallbacks from item titles
            if not email and email_item_id:
                email = _extract_answer_value(answers.get(email_item_id, {})) or ""
            if total_score is None and score_item_id:
                total_score = _safe_float(_extract_answer_value(answers.get(score_item_id, {})))

            # Build answer map
            answer_dict = {}
            for q in questions:
                item_id = q["itemId"]
                answer_dict[item_id] = _extract_answer_value(answers.get(item_id, {}))

            # fraction + percent when max_points is known and > 0
            fraction = ""
            percent = None
            if total_score is not None and max_points > 0:
                fraction = f"{int(total_score) if total_score.is_integer() else total_score}/{int(max_points) if float(max_points).is_integer() else max_points}"
                percent = round((total_score / max_points) * 100, 2)

            structured_responses.append({
                "submitted": resp.get("lastSubmittedTime", "Unknown"),
                "answers": answer_dict,
                "email": email,
                "totalScore": total_score,
                "fraction": fraction,   # e.g., "3/6"
                "percent": percent      # e.g., 50.0
            })

        return {
            "ok": True,
            "form_id": form_id,
            "form_title": (form.get("info") or {}).get("title", "Untitled"),
            "is_quiz": is_quiz,
            "max_points": max_points if max_points > 0 else None,
            "questions": questions,
            "responses": structured_responses,
            "num_questions": len(questions),
            "num_responses": len(structured_responses),
        }

    except Exception as e:
        logger.error("Failed to fetch form: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}
