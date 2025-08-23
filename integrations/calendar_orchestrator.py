import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Optional
from integrations.calendar_create import create_events_from_suggestions
from core.logger import logger

def schedule_from_timetable(agent_output: Dict) -> List[Dict]:
    """
    Schedule events directly from TimetableAgent output.
    Expects:
      agent_output = {
        "suggested_slots": [ { start, end, title, reason, location? }, ... ],
        "metadata": {
          "course_name": str|None,
          "session_purpose": str|None,
          "location_hint": str|None,
          "attendees": list[str],
          "calendar_id": str (default 'primary'),
          ...
        }
      }
    Returns per-slot results from create_events_from_suggestions.
    """
    if not isinstance(agent_output, dict) or "suggested_slots" not in agent_output:
        return [{"ok": False, "error": "Invalid agent output (no suggested_slots)."}]

    slots = agent_output.get("suggested_slots") or []
    meta = agent_output.get("metadata") or {}

    calendar_id = meta.get("calendar_id") or "primary"
    course_name = meta.get("course_name")
    description = meta.get("session_purpose") or "Scheduled by AI assistant."
    attendees = meta.get("attendees") or []
    # If a slot has its own 'location', that will be used; otherwise we may fallback later.
    location_default = meta.get("location_hint")
    color_id = None  # optional

    logger.info("Scheduling %d suggested slots to calendar '%s'", len(slots), calendar_id)

    # Pass directly; create_events_from_suggestions will prefer slot['title']/'location']
    return create_events_from_suggestions(
        slots,
        calendar_id=calendar_id,
        title_prefix="Lesson",       # only used if slot lacks a title
        course_name=course_name,     # only used if slot lacks a title
        description=description,
        attendees=attendees,
        location=location_default,   # slot.location takes precedence
        color_id=color_id,
        assume_free=True             # trust agent suggestions; fastest path
    )
