import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from core.ai_client import chat_completion
from core.logger import logger
from integrations.calendar_tool import fetch_calendar_events


class TimetableAgent:
    def __init__(self, model="openai/gpt-5-chat-latest"):
        self.model = model

    def suggest_lesson_slots(
        self,
        days_ahead: int = 7,
        work_hours: tuple = (9, 17),
        slot_hours: int = 1,
        course_name: str | None = None,
        session_purpose: str | None = None,
        location_hint: str | None = None,
        attendees: list[str] | None = None,      # NEW: suggest default attendees
        calendar_id: str = "primary" 
    ) -> dict:
        """
        Suggest exactly 3 free lesson slots AND include an event title per slot.

        Returns (on success):
        {
          "suggested_slots": [
            {
              "start": "YYYY-MM-DDTHH:MM",
              "end":   "YYYY-MM-DDTHH:MM",
              "title": "Algebra I: Week 2 - Quadratic Basics",
              "reason":"earliest available on Tue morning; avoids staff mtg",
              "location": "Room 204"   // optional if model infers from hint
            }, ...
          ]
        }
        """
        try:
            logger.info(
                "TimetableAgent started (days_ahead=%d, work_hours=%s, slot_hours=%d, course=%s, purpose=%s)",
                days_ahead, work_hours, slot_hours, course_name, session_purpose
            )

            events = fetch_calendar_events(days_ahead=days_ahead)
            if isinstance(events, dict) and events.get("error"):
                logger.error("Calendar fetch error: %s", events.get("error"))
                return {"error": events.get("error")}

            context_bits = []
            if course_name:
                context_bits.append(f"- Course name: {course_name}")
            if session_purpose:
                context_bits.append(f"- Session purpose: {session_purpose}")
            if location_hint:
                context_bits.append(f"- Preferred location: {location_hint}")
            if attendees:
                context_bits.append(f"- Attendees (FYI): {', '.join(attendees)}")
            context_text = "\n".join(context_bits) if context_bits else "- No extra context"

            system_prompt = f"""
            Respond ONLY in valid JSON. Do NOT include any text outside JSON.
            You are a teaching assistant that schedules lessons and also names events for the teacher's calendar.

            Use the constraints and upcoming events to suggest exactly 3 free lesson slots.

            Constraints:
            - Weekdays only (Mon–Fri)
            - Working hours: {work_hours[0]}:00–{work_hours[1]}:00
            - Slot duration: {slot_hours} hour(s)
            - Avoid all conflicts with provided events (busy if overlapping or all-day)
            - Align to 30-minute increments
            - Prefer earliest available times
            - Provide a concise, human-friendly event title (<= 60 chars). If course_name/purpose given, include them briefly.
            - If a location_hint is provided, include it in "location" (optional field).

            Output JSON schema:
            {{
              "suggested_slots": [
                {{
                  "start": "YYYY-MM-DDTHH:MM",
                  "end":   "YYYY-MM-DDTHH:MM",
                  "title": "string",
                  "reason":"string",
                  "location":"string (optional)"
                }},
                {{...}}, {{...}}
              ]
            }}
            """

            user_prompt = (
                "Extra context for naming the events:\n"
                f"{context_text}\n\n"
                "Here are upcoming Google Calendar events (ISO times as available):\n"
                + json.dumps(events)
            )

            raw = chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1200,
            )

            try:
                result = json.loads(raw)

                # minimal validation/sanitization
                slots = result.get("suggested_slots", []) or []
                clean = []
                for s in slots:
                    if not isinstance(s, dict):
                        continue
                    start = (s.get("start") or "").strip()
                    end = (s.get("end") or "").strip()
                    title = (s.get("title") or "").strip()
                    reason = (s.get("reason") or "").strip()
                    location = (s.get("location") or "").strip() or None

                    # must have start/end/title
                    if not (start and end and title):
                        continue

                    # trim overly long titles to be safe
                    if len(title) > 60:
                        title = title[:57].rstrip() + "..."

                    clean.append({
                        "start": start,
                        "end": end,
                        "title": title,
                        "reason": reason,
                        **({"location": location} if location else {})
                    })

                result["suggested_slots"] = clean
                result["metadata"] = {
                    "course_name": course_name,
                    "session_purpose": session_purpose,
                    "location_hint": location_hint,
                    "attendees": attendees or [],
                    "calendar_id": calendar_id,
                    "work_hours": list(work_hours),
                    "slot_hours": slot_hours,
                    "days_ahead": days_ahead
                }

                logger.info("TimetableAgent produced %d suggested slot(s)", len(clean))
                return result

            except json.JSONDecodeError:
                logger.error("Model did not return valid JSON. Raw output: %s", raw)
                return {"error": "Model did not return valid JSON."}

        except Exception as e:
            logger.error("TimetableAgent failed: %s", e, exc_info=True)
            return {"error": f"TimetableAgent failed: {e}"}
