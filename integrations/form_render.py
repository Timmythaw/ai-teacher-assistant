from __future__ import annotations
import csv
import io
from typing import Dict, Any, List


def render_responses_csv_string(form: Dict[str, Any], responses: List[Dict[str, Any]], *, add_bom: bool = False) -> str:
    """
    Minimal CSV renderer that returns only three columns for each response:
    - Form Title
    - Email
    - Total Score

    Inputs:
    - form: Google Form structure (expects form['info']['title'] and form['items']).
    - responses: List of response objects (expects response['answers']).

        Behavior:
        - Prefers response-level fields respondentEmail and totalScore when available.
        - Falls back to matching item titles that contain 'email' (for Email) and 'mark' or 'score'
            (for Total Score), case-insensitive, extracting their answer values.
    - Returns a CSV string with header: Form Title, Email, Total Score.
    - Each row corresponds to one response; Form Title is repeated per row.
    - Never writes to disk.
    """

    # Prepare buffer and writer
    buf = io.StringIO()
    writer = csv.writer(buf)

    form_title = (form or {}).get("info", {}).get("title", "Untitled")

    # Map itemId for email and score by scanning form items' titles
    email_item_id = None
    score_item_id = None
    for item in (form or {}).get("items", []) or []:
        title = str(item.get("title", "")).strip()
        item_id = item.get("itemId")
        lt = title.lower()
        if email_item_id is None and "email" in lt:
            email_item_id = item_id
        if score_item_id is None and ("mark" in lt or "score" in lt):
            score_item_id = item_id

    # Header
    writer.writerow(["Form Title", "Email", "Total Score"])

    # Short-circuit on no responses
    if not (responses and isinstance(responses, list)):
        csv_text = buf.getvalue()
        buf.close()
        return ("\ufeff" + csv_text) if add_bom else csv_text

    def _extract_value(ans_obj: Dict[str, Any]) -> str:
        if not isinstance(ans_obj, dict):
            return ""
        if "textAnswers" in ans_obj and ans_obj.get("textAnswers", {}).get("answers"):
            return "; ".join(
                a.get("value", "") for a in ans_obj["textAnswers"].get("answers", []) if a.get("value")
            )
        if "choiceAnswers" in ans_obj and ans_obj.get("choiceAnswers", {}).get("answers"):
            return "; ".join(
                a.get("value", "") for a in ans_obj["choiceAnswers"].get("answers", []) if a.get("value")
            )
        return ""

    for resp in responses:
        answers = (resp or {}).get("answers", {}) or {}
        # Prefer API-level fields
        email_val = resp.get("respondentEmail") or ""
        score_val = resp.get("totalScore")

        # Fallbacks via item-title detection when necessary
        if not email_val and email_item_id:
            email_val = _extract_value(answers.get(email_item_id, {}))
        if score_val is None and score_item_id:
            score_val = _extract_value(answers.get(score_item_id, {}))

        # Normalize values to strings
        if score_val is None:
            score_val_str = ""
        else:
            score_val_str = str(score_val)
        writer.writerow([form_title, email_val, score_val_str])

    csv_text = buf.getvalue()
    buf.close()
    if add_bom:
        return "\ufeff" + csv_text
    return csv_text
