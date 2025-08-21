import datetime
import os, json
import sys

sys.path.append('..')
from client import create_client
client = create_client()

def fetch_calendar_events(days_ahead=7):
    from tools.calendar_tool import fetch_calendar_events
    return fetch_calendar_events(days_ahead)

system_prompt = """
You are a teaching assistant agent that helps schedule lessons.
You have access to this tool:

Tool: fetch_calendar_events(days_ahead: int)
- Returns upcoming events from the teacher's Google Calendar.

Rules:
- If you need to call the tool, respond ONLY in JSON:
  {"action": "fetch_calendar_events", "args": {"days_ahead": 7}}
- If you are given calendar events, analyze them and suggest 3 suitable 1-hour lesson slots
  during weekdays (Mon–Fri), 9am–5pm, avoiding conflicts.
"""

def timetable_agent(user_request: str, openai_key : str):
    sys.path.append('..')
    from client import create_client
    client = create_client(openai_key)

    # Step 1: Ask GPT what to do
    response = client.chat.completions.create(
        model="openai/gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request}
        ],
        temperature=0
    )

    assistant_reply = response.choices[0].message.content
    print("Assistant raw reply:", assistant_reply)

    # Step 2: Check if it's a tool call
    try:
        action = json.loads(assistant_reply)
        if action.get("action") == "fetch_calendar_events":
            print("Tool requested:", action)
            result = fetch_calendar_events(**action["args"])

            # Step 3: Explicit second call to GPT to analyze events
            followup = client.chat.completions.create(
                model="openai/gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_request},
                    {"role": "assistant", "content": "Calendar events retrieved."},
                    {"role": "system", "content": f"Here are the calendar events: {json.dumps(result)}"}
                ],
                temperature=0
            )
            return followup.choices[0].message.content
    except Exception:
        # Not a tool call, just return GPT’s direct answer
        return assistant_reply

