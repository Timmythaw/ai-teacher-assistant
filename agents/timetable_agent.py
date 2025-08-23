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

    def suggest_lesson_slots(self, days_ahead: int = 7, work_hours: tuple = (9, 17), slot_hours: int = 1) -> dict:
        try:
            logger.info(
                "TimetableAgent started (days_ahead=%d, work_hours=%s, slot_hours=%d)",
                days_ahead,
                work_hours,
                slot_hours,
            )

            events = fetch_calendar_events(days_ahead=days_ahead)
            if isinstance(events, dict) and events.get("error"):
                logger.error("Calendar fetch error: %s", events.get("error"))
                return {"error": events.get("error")}

            system_prompt = f"""
            Respond ONLY in valid JSON.
            You are a teaching assistant agent that helps schedule lessons.
            Given upcoming Google Calendar events and constraints, suggest exactly 3 free lesson slots.

            Constraints:
            - Weekdays only (Mon–Fri)
            - Working hours: {work_hours[0]}:00–{work_hours[1]}:00
            - Slot duration: {slot_hours} hour(s)
            - Avoid all conflicts with provided events (busy if overlapping or all-day)
            - Align to 30-minute increments
            - Prefer earliest available times

            Output JSON schema:
            {{
              "suggested_slots": [
                {{"start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM", "reason": "..."}},
                {{"start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM", "reason": "..."}},
                {{"start": "YYYY-MM-DDTHH:MM", "end": "YYYY-MM-DDTHH:MM", "reason": "..."}}
              ]
            }}
            """

            user_prompt = "Here are upcoming Google Calendar events (ISO times as available):\n" + json.dumps(events)

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
                logger.info(
                    "TimetableAgent produced %d suggested slot(s)",
                    len(result.get("suggested_slots", [])),
                )
                return result
            except json.JSONDecodeError:
                logger.error("Model did not return valid JSON. Raw output: %s", raw)
                return {"error": "Model did not return valid JSON."}

        except Exception as e:
            logger.error("TimetableAgent failed: %s", e, exc_info=True)
            return {"error": f"TimetableAgent failed: {e}"}


"""
tt_agent = TimetableAgent()
slots = tt_agent.suggest_lesson_slots(days_ahead=7, work_hours=(9, 17), slot_hours=1)
print(slots)
"""
