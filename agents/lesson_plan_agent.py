import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from core.ai_client import chat_completion
from core.pdf_tool import extract_text_from_pdf
from core.logger import logger

class LessonPlanAgent:
    def __init__(self, model="openai/gpt-5-chat-latest"):
        self.model = model

    def generate_plan(self, inputs: dict, study_duration_weeks, num_students, sections_per_week) -> dict:
        try:
            logger.info("LessonPlanAgent started with inputs: %s", inputs)
            combined_text = ""

            if "course_outline" in inputs:
                text = extract_text_from_pdf(inputs["course_outline"])
                logger.info("Extracted course outline: %s (length=%d)",
                            inputs["course_outline"], len(text))
                combined_text += text + "\n"
                
            if "lecture_notes" in inputs:
                text = extract_text_from_pdf(inputs["lecture_notes"])
                logger.info("Extracted lecture notes: %s (length=%d)",
                            inputs["lecture_notes"], len(text))
                combined_text += text + "\n"

            if not combined_text.strip():
                logger.warning("No valid text extracted from provided PDFs")
                return {"error": "No valid text extracted from provided PDFs."}

            system_prompt = f"""
            Respond ONLY in valid JSON.
            You are an expert pedagogy designer. Create a practical, well-structured lesson plan series using the provided source content.
            Generate a structured lesson plan JSON including:
            - total_duration: {study_duration_weeks} (weeks)
            - class_size: {num_students} (students)
            - sections_per_week: {sections_per_week}
            - weekly_schedule (list of [week, topic, activities, resources])
            - external_resources (books, websites, videos)

            Requirements:
            1) Provide an overview with goals and success criteria tailored to the class size.
            2) Break down the plan by week w    ith clear learning objectives, key topics, and vocabulary.
            3) For each week, divide into exactly {sections_per_week} section(s). For each section include:
            - Activities (at least one teacher-led, one student-centered, one collaborative activity)
            - Materials/resources
            - Differentiation for mixed abilities and larger group management if applicable
            - Assessment (formative + one summative suggestion across the duration)
            4) Add homework/extension ideas and optional enrichment.
            5) Keep it concise and actionable. Use markdown headings and bullet points.
            """

            raw = chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": combined_text}
                ],
                temperature=0.4,
                max_tokens=4000
            )

            try:
                result = json.loads(raw)
                logger.info("LessonPlanAgent successfully generated lesson plan (weeks=%s, sections_per_week=%s)",
                            result.get("total_duration"), result.get("sections_per_week"))
                return result
            
            except json.JSONDecodeError:
                logger.error("Model did not return valid JSON. Raw output: %s", raw)
                return {"error": "Model did not return valid JSON."}

        except Exception as e:
            logger.error("LessonPlanAgent failed: %s", e, exc_info=True)
            return {"error": f"LessonPlanAgent failed: {e}"}

lp_agent = LessonPlanAgent()
plan = lp_agent.generate_plan({"course_outline": os.environ.get("COURSE_OUTLINE_PATH")}, 8, 30, 1)
print(plan)