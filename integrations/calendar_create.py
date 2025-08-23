import datetime as dt
import hashlib
from typing import List, Dict, Optional
from googleapiclient.errors import HttpError

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo  # type: ignore
except Exception:  # pragma: no cover
    ZoneInfo = None

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.google_client import get_google_service
from core.logger import logger


# ---------------------- Helpers: timezone & time ----------------------

def get_user_timezone(service, calendar_id: str = "primary") -> str:
    """
    Fetch the user's calendar timezone from Google Calendar.
    Falls back to 'UTC' if unavailable.
    """
    try:
        cal = service.calendars().get(calendarId=calendar_id).execute()
        tz = cal.get("timeZone", "UTC")
        logger.info("Detected calendar timezone: %s", tz)
        return tz
    except Exception as e:
        logger.warning("Could not fetch timezone, defaulting to UTC: %s", e)
        return "UTC"


def _parse_local_iso_short(s: str, tz: str) -> str:
    """
    Convert 'YYYY-MM-DDTHH:MM' (no seconds, no tz) into RFC3339 string in the given timezone.
    Example -> '2025-08-23T10:00' + 'Asia/Bangkok' => '2025-08-23T10:00:00+07:00'
    """
    if not s or "T" not in s:
        raise ValueError(f"Invalid datetime string: {s}")

    y, m, rest = s.split("-", 2)
    d, hm = rest.split("T")
    hh, mm = hm.split(":")
    naive = dt.datetime(int(y), int(m), int(d), int(hh), int(mm))

    if ZoneInfo:
        aware = naive.replace(tzinfo=ZoneInfo(tz))
        return aware.isoformat()
    else:
        # Fallback: keep naive; Google may interpret as default calendar TZ (not ideal).
        # Prefer Python 3.9+ with zoneinfo / tzdata installed.
        return naive.isoformat()


def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    """
    Interval overlap check on ISO 8601 strings (safe because ISO sorts lexicographically).
    """
    return not (a_end <= b_start or a_start >= b_end)


# ---------------------- Idempotency ----------------------

def _idempotency_key(title: str, start_rfc3339: str, end_rfc3339: str) -> str:
    raw = f"{title}|{start_rfc3339}|{end_rfc3339}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _exists_with_key(service, calendar_id: str, idem_key: str) -> bool:
    """
    Check for an existing event bearing the same idempotency key in private extended properties.
    We scan a 30-day forward window and filter for the key.
    """
    try:
        now = dt.datetime.utcnow().isoformat() + "Z"
        horizon = (dt.datetime.utcnow() + dt.timedelta(days=30)).isoformat() + "Z"
        events = service.events().list(
            calendarId=calendar_id,
            timeMin=now, timeMax=horizon,
            singleEvents=True, orderBy="startTime", maxResults=250
        ).execute().get("items", [])
        for ev in events:
            props = ev.get("extendedProperties", {}).get("private", {})
            if props.get("idem_key") == idem_key:
                return True
        return False
    except Exception as e:
        # If listing fails for some reason, we just skip dedupe to avoid blocking.
        logger.warning("Idempotency existence check failed: %s", e)
        return False


# ---------------------- Optional conflict check ----------------------

def _find_conflicts(service, start_rfc3339: str, end_rfc3339: str, calendar_id: str = "primary") -> List[Dict]:
    """
    Fetch events in the window to detect any overlap.
    """
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_rfc3339,
        timeMax=end_rfc3339,
        singleEvents=True,
        orderBy="startTime",
        maxResults=50,
    ).execute()
    return events_result.get("items", [])


# ---------------------- Public API ----------------------

def create_event_for_slot(
    slot: Dict,
    *,
    service=None,
    calendar_id: str = "primary",
    title: str = "Lesson",
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    location: Optional[str] = None,
    reminders_override: bool = True,
    color_id: Optional[str] = None,
    assume_free: bool = True  # trust the agent's suggestions by default
) -> Dict:
    """
    Create a single calendar event from a slot shaped like:
      slot = {"start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM", "reason": "..."}
    Returns: {ok, event_id, html_link} or {ok: False, error}
    """
    try:
        if service is None:
            service = get_google_service("calendar", "v3")

        # Detect user's calendar timezone
        tz = get_user_timezone(service, calendar_id)

        # Convert naive local strings to RFC3339 in user's TZ
        start_rfc3339 = _parse_local_iso_short(slot.get("start", ""), tz)
        end_rfc3339 = _parse_local_iso_short(slot.get("end", ""), tz)

        # Idempotency: avoid duplicate inserts if retried
        idem_key = _idempotency_key(title, start_rfc3339, end_rfc3339)
        if _exists_with_key(service, calendar_id, idem_key):
            logger.info("Event already exists for key=%s; skipping create.", idem_key)
            return {"ok": True, "deduped": True, "event_id": None, "html_link": None}

        # Optional race-check only if NOT assuming free
        if not assume_free:
            conflicts = _find_conflicts(service, start_rfc3339, end_rfc3339, calendar_id)
            for ev in conflicts:
                ev_start = ev["start"].get("dateTime") or ev["start"].get("date")
                ev_end = ev["end"].get("dateTime") or ev["end"].get("date")
                # All-day events return dates without times; treat as blocking the day.
                if "T" not in ev_start or "T" not in ev_end:
                    return {"ok": False, "error": "Conflicts with an all-day event."}
                if _overlaps(start_rfc3339, end_rfc3339, ev_start, ev_end):
                    title_conf = ev.get("summary", "")
                    return {"ok": False, "error": f"Conflicts with: {title_conf or 'busy time'}."}

        body = {
            "summary": title,
            "description": description or slot.get("reason", ""),
            "start": {"dateTime": start_rfc3339},
            "end": {"dateTime": end_rfc3339},
            "extendedProperties": {"private": {"idem_key": idem_key}},  # idempotency marker
        }
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": a} for a in attendees if a]
        if reminders_override:
            body["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "email", "minutes": 60},
                ],
            }
        if color_id:
            body["colorId"] = color_id  # Valid values: '1'..'11'

        created = service.events().insert(
            calendarId=calendar_id,
            body=body,
            sendUpdates="all" if attendees else "none"
        ).execute()

        logger.info("Created event %s (%s)", created.get("id"), created.get("htmlLink"))
        return {"ok": True, "event_id": created.get("id"), "html_link": created.get("htmlLink")}

    except HttpError as e:
        logger.error("Calendar API error (create event): %s", e)
        return {"ok": False, "error": f"Calendar API error: {e}"}
    except Exception as e:
        logger.error("Failed to create event: %s", e, exc_info=True)
        return {"ok": False, "error": f"Failed to create event: {e}"}


def create_events_from_suggestions(
    suggested_slots: List[Dict],
    *,
    calendar_id: str = "primary",
    title_prefix: str = "Class",
    course_name: Optional[str] = None,
    description: Optional[str] = None,
    attendees: Optional[List[str]] = None,
    location: Optional[str] = None,
    color_id: Optional[str] = None,
    assume_free: bool = True  # trust suggestions in bulk
) -> List[Dict]:
    """
    Bulk create events from TimetableAgent's 'suggested_slots'.
    Returns a list of per-slot results:
      [{slot_index, start, end, ok, event_id?, html_link?, error?, deduped?}, ...]
    """
    service = get_google_service("calendar", "v3")
    results = []
    for i, slot in enumerate(suggested_slots, start=1):
        title = slot.get("title") or (f"{title_prefix}: {course_name}" if course_name else title_prefix)
        location = slot.get("location") or location  # prefer per-slot location if provided
        res = create_event_for_slot(
            slot,
            service=service,
            calendar_id=calendar_id,
            title=title,
            description=description,
            attendees=attendees,
            location=location,
            color_id=color_id,
            assume_free=assume_free
        )
        results.append({
            "slot_index": i,
            "start": slot.get("start"),
            "end": slot.get("end"),
            **res
        })
    return results
