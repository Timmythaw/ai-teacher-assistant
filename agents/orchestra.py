import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from core.ai_client import chat_completion

def validate_json_schema(output_str, schema_keys):
    try:
        data = json.loads(output_str)
        for key in schema_keys:
            if key not in data:
                return False, None
        return True, data
    except Exception:
        return False, None

class Orchestrator:
    def __init__(self, model="openai/gpt-5-chat-latest"):
        self.model = model

    def plan(self, teacher_request: str) -> dict:
        system_prompt = """
        You are a planner agent for a teaching assistant.
        Take the teacher's request and decompose it into subtasks.
        Respond ONLY in JSON with keys: ["tasks"].
        """

        raw_output = chat_completion(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": teacher_request}
            ],
            temperature=0
        )

        ok, data = validate_json_schema(raw_output, ["tasks"])
        if not ok:
            raise ValueError("Planner did not return valid JSON. Got: " + raw_output)
        return data

    def execute(self, tasks: list, agents: dict):
        results = {}
        for t in tasks:
            action = t["action"]
            inp = t["input"]
            if action in agents:
                results[action] = agents[action](inp)
            else:
                results[action] = f"No agent found for {action}"
        return results

    def reflect(self, results: dict):
        for k, v in results.items():
            if not v:
                return False, f"{k} produced empty result"
        return True, results