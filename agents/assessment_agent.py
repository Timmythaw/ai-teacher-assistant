import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from core.ai_client import chat_completion
from core.pdf_tool import extract_text_from_pdf

class AssessmentAgent:
    def __init__(self, model="openai/gpt-5-chat-latest"):
        self.model = model

    def generate_assessment(self, course_material: str, options: dict) -> dict:
        try:
            # PDF or raw text
            if course_material.endswith(".pdf"):
                material_text = extract_text_from_pdf(course_material)
            else:
                material_text = course_material

            if not material_text.strip():
                return {"error": "No valid course material found."}

            system_prompt = """
            You are an assessment designer.
            Create an assessment based on provided material.
            JSON structure should include:
            - type (MCQ, ShortAnswer, Project)
            - difficulty
            - questions: [{q, options(if MCQ), answer}]
            - rubric: [{criteria, points}] (if rubric requested)
            """

            user_prompt = f"""
            Create a {options.get('type', 'MCQ')} assessment.
            Difficulty: {options.get('difficulty', 'Medium')}.
            Number of questions: {options.get('count', 5)}.
            Include rubric: {options.get('rubric', True)}.
            """

            raw = chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": material_text},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4
            )

            return json.load(raw)

        except json.JSONDecodeError:
            return {"error": "Model did not return valid JSON."}
        except Exception as e:
            return {"error": f"AssessmentAgent failed: {e}"}