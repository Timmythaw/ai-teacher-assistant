import os
from typing import Dict, Any, Optional
from core.logger import logger
from core.google_client import get_google_service
from integrations.forms_fetch import fetch_form_structure, fetch_all_responses
from integrations.form_utils import extract_form_id


def get_form_full_info(link_or_id: str) -> Dict[str, Any]:
    """
    Fetch form structure and responses, returning all relevant info:
    - form_title
    - questions: [{itemId, title, type}]
        - responses: [{submitted, answers: {itemId: value}, marks, email}]
            Note:
            - email prefers response.respondentEmail when available (requires email collection enabled),
                falling back to the value of a question whose title contains "email".
            - marks prefers response.totalScore for quiz forms, falling back to any question with title
                containing "mark" or "score" if present in answers.
    """
    try:
        form_id = extract_form_id(link_or_id)
        if not form_id:
            return {"ok": False, "error": "Invalid form link or ID"}

        service = get_google_service("forms", "v1")
        form = fetch_form_structure(service, form_id)
        responses = fetch_all_responses(service, form_id)

        # Extract questions with type
        questions = []
        for item in form.get("items", []):
            qtype = "Unknown"
            if "questionItem" in item:
                question = item["questionItem"].get("question", {})
                if "textQuestion" in question:
                    qtype = "Short Answer"
                elif "choiceQuestion" in question:
                    qtype = "Multiple Choice"
                elif "paragraphQuestion" in question:
                    qtype = "Paragraph"
            questions.append({
                "itemId": item.get("itemId"),
                "title": item.get("title", "Untitled Question"),
                "type": qtype
            })

        # Extract responses with answers, marks, emails
        structured_responses = []
        for resp in responses:
            answers = resp.get("answers", {})
            answer_dict = {}
            # Prefer authoritative API fields when present
            marks = resp.get("totalScore")
            email = resp.get("respondentEmail")
            for q in questions:
                item_id = q["itemId"]
                title = q["title"]
                answer = answers.get(item_id, {})
                value = ""
                if "textAnswers" in answer:
                    value = "; ".join(a.get("value", "") for a in answer["textAnswers"]["answers"] if a.get("value"))
                elif "choiceAnswers" in answer:
                    value = "; ".join(a.get("value", "") for a in answer["choiceAnswers"]["answers"] if a.get("value"))
                answer_dict[item_id] = value
                # Fallback detection of marks and email by question title when API fields are absent
                title_l = title.lower()
                if marks is None and ("mark" in title_l or "score" in title_l):
                    marks = value
                if (not email) and ("email" in title_l):
                    email = value
            structured_responses.append({
                "submitted": resp.get("lastSubmittedTime", "Unknown"),
                "answers": answer_dict,
                "marks": marks,
                "email": email
            })

        return {
            "ok": True,
            "form_id": form_id,
            "form_title": form.get("info", {}).get("title", "Untitled"),
            "questions": questions,
            "responses": structured_responses,
            "num_questions": len(questions),
            "num_responses": len(structured_responses)
        }
    except Exception as e:
        logger.error("Failed to fetch form: %s", e, exc_info=True)
        return {"ok": False, "error": str(e)}
