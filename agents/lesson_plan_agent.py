import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
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

            system_prompt = (
                "Respond ONLY in valid JSON.\n"
                "You are an expert pedagogy designer. Create a practical, well-structured lesson plan series using the provided source content.\n\n"
                "Return ONLY a JSON object with these keys (omit keys that are not applicable):\n"
                "- title (string)\n"
                "- metadata (object) with optional fields: course, chapter, instructor, academic_year, school\n"
                "- lesson_title (string)\n"
                f"- total_duration (number of weeks, default {study_duration_weeks})\n"
                f"- class_size (number of students, default {num_students})\n"
                f"- sections_per_week (number, default {sections_per_week})\n"
                "- learning_objectives (array of strings)\n"
                "- key_concepts (object) including optional fields such as: definition, role_in_sdlc, goals, importance, reference_resources (array of links/strings)\n"
                "- teaching_strategies (array of strings, e.g., Lecture with Diagram, Class Discussion, Think-Pair-Share)\n"
                "- teaching_activities (array of objects). Each activity object: \n"
                "  { title, duration_minutes (number), description (string, optional), steps (array of strings) }\n"
                "- assessment_evaluation (string or array of strings)\n"
                "- materials_needed (array of strings)\n"
                "- weekly_schedule (array of week objects). Each week object should have: \n"
                "  - week (number)\n  - topic (string)\n  - learning_objectives (array of strings)\n  - vocabulary (array of strings, optional)\n"
                "  - activities (array of strings or objects)\n  - materials (array of strings)\n  - differentiation (array of strategies)\n  - assessment (string or array)\n  - homework (string or array)\n  - sections (array of objects, length exactly sections_per_week, each with title, activities, materials, assessment)\n"
                "- external_resources (array of strings or objects: books, websites, videos)\n\n"
                "Constraints:\n- Keep strings concise and actionable.\n- Use only double quotes.\n- Do NOT include any prose, explanations, code fences, or markdown—return a single JSON object only."
            )

            raw = chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": combined_text}
                ],
                temperature=0.4,
                max_tokens=4000
            )

            # Parse strictly first, then sanitize if needed
            parsed = None
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
                candidate = fence.group(1) if fence else None
                if not candidate:
                    s = raw.find('{')
                    e = raw.rfind('}')
                    if s != -1 and e != -1 and e > s:
                        candidate = raw[s:e+1]
                if candidate:
                    norm = candidate
                    norm = norm.replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'")
                    norm = re.sub(r",\s*([}\]])", r"\1", norm)
                    try:
                        parsed = json.loads(norm)
                    except json.JSONDecodeError:
                        logger.error("Sanitized JSON still invalid. Raw: %s", raw)
                        return {"error": "Model did not return valid JSON.", "raw": raw}
                else:
                    logger.error("No JSON object could be extracted. Raw: %s", raw)
                    return {"error": "Model did not return valid JSON.", "raw": raw}

            if not isinstance(parsed, dict):
                logger.error("Parsed JSON is not an object. Parsed: %s", parsed)
                return {"error": "Model did not return a JSON object.", "raw": raw}

            # Ensure expected keys with defaults
            parsed.setdefault("title", "Lesson Plan")
            parsed.setdefault("total_duration", study_duration_weeks)
            parsed.setdefault("class_size", num_students)
            parsed.setdefault("sections_per_week", sections_per_week)
            parsed.setdefault("weekly_schedule", [])
            parsed.setdefault("external_resources", [])

            logger.info(
                "LessonPlanAgent successfully generated lesson plan (weeks=%s, sections_per_week=%s)",
                parsed.get("total_duration"), parsed.get("sections_per_week")
            )
            return parsed

        except Exception as e:
            logger.error("LessonPlanAgent failed: %s", e, exc_info=True)
            return {"error": f"LessonPlanAgent failed: {e}"}

