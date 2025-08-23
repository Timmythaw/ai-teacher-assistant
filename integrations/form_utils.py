import re
from typing import List, Tuple, Dict, Any, Optional

def extract_form_id(link_or_id: str) -> Optional[str]:
    if not link_or_id:
        return None
    s = link_or_id.strip()
    if "/" not in s and len(s) >= 20:
        return s
    m = re.search(r"/forms/d/([a-zA-Z0-9_-]+)", s)
    return m.group(1) if m else None

def extract_questions_in_order(form: Dict[str, Any]) -> List[Tuple[str, str]]:
    items = form.get("items", []) or []
    ordered: List[Tuple[str, str]] = []
    for it in items:
        item_id = it.get("itemId")
        title = it.get("title") or "Untitled"
        if item_id:
            ordered.append((item_id, title))
    return ordered

def render_answer_cell(answer_item: Optional[Dict[str, Any]]) -> str:
    if not answer_item:
        return ""
    ta = answer_item.get("textAnswers")
    if ta:
        return "; ".join(a.get("value","") for a in ta.get("answers",[]) if a.get("value"))
    ca = answer_item.get("choiceAnswers")
    if ca:
        return "; ".join(a.get("value","") for a in ca.get("answers",[]) if a.get("value"))
    return ""
