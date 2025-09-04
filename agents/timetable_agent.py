import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime as dt
from core.logger import logger
from integrations.calendar_tool import fetch_calendar_events
from integrations.calendar_create import get_user_timezone
from core.google_client import get_google_service
from core.pdf_tool import extract_text_from_pdf


def _pick(obj, keys, default=None):
    for k in keys:
        if isinstance(obj, dict) and k in obj and obj[k] is not None:
            return obj[k]
    return default

def _extract_minimal_plan(plan_or_path) -> dict:
    """Extract minimal fields from lesson plan JSON or a PDF path.
    Returns { title, duration_weeks, sections_per_week, week_names[] }.
    """
    title = "Lesson Plan"
    duration_weeks = 8
    sections_per_week = 1
    week_names: list[str] = []

    try:
        if isinstance(plan_or_path, dict):
            plan = plan_or_path
        elif isinstance(plan_or_path, str) and plan_or_path.lower().endswith(".pdf"):
            # Heuristic parse from PDF text
            text = extract_text_from_pdf(plan_or_path) or ""
            # Find duration like "8 week" or "8 weeks"
            import re
            m = re.search(r"(\d{1,2})\s*week", text, re.IGNORECASE)
            if m:
                duration_weeks = int(m.group(1))
            # Find section per week pattern (optional)
            m2 = re.search(r"sections?\s*per\s*week\s*[:=]?\s*(\d{1,2})", text, re.IGNORECASE)
            if m2:
                sections_per_week = int(m2.group(1))
            # Find week headings
            for i in range(1, duration_weeks + 1):
                pat = re.compile(rf"Week\s*{i}[:\-\s]+([^\n\r]{0,80})", re.IGNORECASE)
                mm = pat.search(text)
                if mm:
                    week_names.append(f"Week {i}: {mm.group(1).strip()}")
                else:
                    week_names.append(f"Week {i}")
            # Title fallback from first heading
            t = re.search(r"Lesson\s*Plan[:\-\s]*(.+)$", text, re.IGNORECASE)
            if t:
                title = t.group(1).strip()[:60]
            return {
                "title": title,
                "duration_weeks": duration_weeks,
                "sections_per_week": sections_per_week,
                "week_names": week_names,
            }
        else:
            # Unsupported type
            plan = {}

        # JSON-based extraction
        title = _pick(plan, ["lesson_title", "title", "name"], title)
        duration_weeks = int(_pick(plan, ["total_duration", "weeks", "duration_weeks"], duration_weeks))
        sections_per_week = int(_pick(plan, ["sections_per_week", "sectionsPerWeek"], sections_per_week))
        weekly = _pick(plan, ["weekly_schedule", "weeks_schedule", "plan", "weekly"], []) or []
        if isinstance(weekly, list) and weekly:
            week_names = []
            for i, w in enumerate(weekly, start=1):
                topic = _pick(w, ["topic", "title"], None)
                label = _pick(w, ["week", "label"], i)
                if topic:
                    week_names.append(f"Week {label}: {topic}")
                else:
                    week_names.append(f"Week {label}")
        else:
            week_names = [f"Week {i}" for i in range(1, duration_weeks + 1)]

        return {
            "title": title,
            "duration_weeks": duration_weeks,
            "sections_per_week": sections_per_week,
            "week_names": week_names,
        }
    except Exception as e:
        logger.warning("Minimal plan extraction failed, using defaults: %s", e)
        return {
            "title": title,
            "duration_weeks": duration_weeks,
            "sections_per_week": sections_per_week,
            "week_names": [f"Week {i}" for i in range(1, duration_weeks + 1)],
        }

def _overlaps(a_start: dt.datetime, a_end: dt.datetime, b_start: dt.datetime, b_end: dt.datetime) -> bool:
    return not (a_end <= b_start or a_start >= b_end)

def _next_monday(d: dt.date) -> dt.date:
    wd = d.weekday()  # Mon=0
    delta = (7 - wd) % 7
    if delta == 0:
        delta = 7
    return d + dt.timedelta(days=delta)


class TimetableAgent:
    llama_model = os.getenv("LLAMA_MODEL", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    def __init__(self, model=llama_model):
        self.model = model

    def suggest_consistent_schedule(
        self,
        plan_or_pdf,
        *,
        work_hours: tuple[int, int] = (9, 17),
        slot_hours: int = 1,
        calendar_id: str = "primary",
        location_hint: str | None = None,
        attendees: list[str] | None = None,
        start_from_next_monday: bool = True,
    ) -> dict:
        """
        Build a consistent weekly timetable from a lesson plan (JSON or PDF path).
        - Extract only title, duration_weeks, sections_per_week, week_names.
        - Scan calendar for duration_weeks * 7 days.
        - Choose consistent weekday/time combos (sections_per_week distinct slots) across all weeks.
        - Output format compatible with calendar_orchestrator.
        """
        try:
            # 1) Minimal plan
            meta = _extract_minimal_plan(plan_or_pdf)
            title = meta.get("title") or "Lesson"
            weeks = int(meta.get("duration_weeks") or 8)
            sections_per_week = int(meta.get("sections_per_week") or 1)
            week_names = meta.get("week_names") or [f"Week {i}" for i in range(1, weeks + 1)]

            # 2) Calendar & TZ
            service = get_google_service("calendar", "v3")
            #tz = get_user_timezone(service, calendar_id)
            #now = dt.datetime.now(dt.timezone.utc).astimezone(dt.timezone(dt.timedelta(0)))  # placeholder tz aware UTC
            today_local = dt.datetime.now().date()
            base_monday = _next_monday(today_local) if start_from_next_monday else today_local

            # 3) Fetch events for the whole span
            days_ahead = max(7, weeks * 7)
            events = fetch_calendar_events(days_ahead=days_ahead)
            if isinstance(events, dict) and events.get("error"):
                return {"error": events.get("error")}

            # normalize events -> list of (start_dt, end_dt) in local date-time terms
            busy: list[tuple[dt.datetime, dt.datetime]] = []
            for ev in events or []:
                s = (ev.get("start") or {})
                e = (ev.get("end") or {})
                s_val = s.get("dateTime") or s.get("date")
                e_val = e.get("dateTime") or e.get("date")
                if not (s_val and e_val):
                    continue
                # Handle all-day (YYYY-MM-DD)
                if "T" not in s_val:
                    d = dt.datetime.strptime(s_val, "%Y-%m-%d").date()
                    start_dt = dt.datetime(d.year, d.month, d.day, 0, 0)
                else:
                    # Trim seconds/timezone if present; keep local naive for overlap checks
                    s_core = s_val.replace("Z", "").split("+", 1)[0]
                    start_dt = dt.datetime.strptime(s_core[:16], "%Y-%m-%dT%H:%M")
                if "T" not in e_val:
                    d2 = dt.datetime.strptime(e_val, "%Y-%m-%d").date()
                    end_dt = dt.datetime(d2.year, d2.month, d2.day, 23, 59)
                else:
                    e_core = e_val.replace("Z", "").split("+", 1)[0]
                    end_dt = dt.datetime.strptime(e_core[:16], "%Y-%m-%dT%H:%M")
                busy.append((start_dt, end_dt))

            # 4) Candidate generator (Mon-Fri, 30-min increments)
            def candidate_starts():
                for wd in range(0, 5):  # Mon..Fri
                    for hh in range(work_hours[0], work_hours[1]):
                        for mm in (0, 30):
                            if hh + slot_hours > work_hours[1]:
                                continue
                            yield wd, hh, mm

            # 5) Check a single weekly timeslot for all weeks
            def timeslot_is_free(wd: int, hh: int, mm: int) -> bool:
                for w in range(weeks):
                    day = base_monday + dt.timedelta(days=wd + 7 * w)
                    start_dt = dt.datetime(day.year, day.month, day.day, hh, mm)
                    end_dt = start_dt + dt.timedelta(hours=slot_hours)
                    for (bs, be) in busy:
                        if _overlaps(start_dt, end_dt, bs, be):
                            return False
                return True

            # 6) Pick N distinct consistent timeslots
            chosen: list[tuple[int, int, int]] = []
            for wd, hh, mm in candidate_starts():
                if timeslot_is_free(wd, hh, mm):
                    chosen.append((wd, hh, mm))
                    if len(chosen) >= sections_per_week:
                        break

            if len(chosen) < sections_per_week:
                logger.warning("Only found %d/%d consistent weekly slots", len(chosen), sections_per_week)

            # 7) Build suggested_slots across weeks
            weekday_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            suggested: list[dict] = []
            for w in range(weeks):
                for si, (wd, hh, mm) in enumerate(chosen, start=1):
                    day = base_monday + dt.timedelta(days=wd + 7 * w)
                    start_dt = dt.datetime(day.year, day.month, day.day, hh, mm)
                    end_dt = start_dt + dt.timedelta(hours=slot_hours)
                    start_str = start_dt.strftime("%Y-%m-%dT%H:%M")
                    end_str = end_dt.strftime("%Y-%m-%dT%H:%M")
                    wlabel = week_names[w] if w < len(week_names) else f"Week {w+1}"
                    # Use only the week/topic label to keep calendar titles short
                    stitle = f"{wlabel}"
                    reason = f"Consistent weekly slot on {weekday_name[wd]} {hh:02d}:{mm:02d} avoiding conflicts"
                    slot = {
                        "start": start_str,
                        "end": end_str,
                        "title": stitle[:60],
                        "reason": reason,
                    }
                    if location_hint:
                        slot["location"] = location_hint
                    suggested.append(slot)

            result = {
                "suggested_slots": suggested,
                "metadata": {
                    "lesson_title": title,
                    "duration_weeks": weeks,
                    "sections_per_week": sections_per_week,
                    "work_hours": list(work_hours),
                    "slot_hours": slot_hours,
                    "calendar_id": calendar_id,
                    "location_hint": location_hint,
                    "attendees": attendees or [],
                    "base_monday": base_monday.isoformat(),
                }
            }
            logger.info("Suggested %d slots over %d week(s)", len(suggested), weeks)
            return result

        except Exception as e:
            logger.error("TimetableAgent failed: %s", e, exc_info=True)
            return {"error": f"TimetableAgent failed: {e}"}
