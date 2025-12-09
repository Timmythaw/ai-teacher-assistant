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
    "You are an expert CurriculumArchitect agent. You have just completed detailed lesson planning. "
    "Now structure your comprehensive lesson plan into a standardized JSON format for storage and rendering.\n\n"
    
    "Respond ONLY in valid JSON.\n\n"
    
    "Return a JSON object with these keys:\n\n"
    
    "- title (string): Course title\n"
    "- metadata (object): {\n"
    "    course: string,\n"
    "    instructor: string (optional),\n"
    "    academic_year: string (optional),\n"
    "    grade_level: string (optional),\n"
    "    curriculum_standards: array of strings (optional)\n"
    "  }\n"
    
    f"- total_duration (number): {study_duration_weeks} weeks\n"
    f"- class_size (number): {num_students} students\n"
    f"- sections_per_week (number): {sections_per_week}\n"
    "- teaching_approach (string): e.g., 'Mixed', 'Inquiry-Based', 'Project-Based'\n"
    
    "- learning_objectives (array of strings): 2-4 measurable objectives using action verbs\n"
    
    "- key_concepts (object): {\n"
    "    definition: string (optional),\n"
    "    core_topics: array of strings,\n"
    "    prerequisites: array of strings (optional),\n"
    "    importance: string (optional),\n"
    "    reference_resources: array of objects [{ title, url, type }] (optional)\n"
    "  }\n"
    
    "- teaching_strategies (array of strings): e.g., ['Direct Instruction', 'Think-Pair-Share', 'Hands-on Lab']\n"
    
    "- teaching_activities (array of objects): [{\n"
    "    title: string,\n"
    "    duration_minutes: number,\n"
    "    description: string,\n"
    "    steps: array of strings,\n"
    "    learning_outcomes: array of strings,\n"
    "    materials: array of strings (optional)\n"
    "  }]\n"
    
    "- materials_needed (array of objects): [{\n"
    "    item: string,\n"
    "    quantity: string or number (optional),\n"
    "    source: string (optional),\n"
    "    page_reference: string (optional)\n"
    "  }]\n"
    
    "- weekly_schedule (array of week objects): [{\n"
    "    week: number,\n"
    "    topic: string,\n"
    "    learning_objectives: array of strings,\n"
    "    vocabulary: array of strings (optional),\n"
    "    activities: array of objects [{ name, duration_minutes, type }],\n"
    "    timeline: array of objects [{ time_range, activity, instructor_notes }],\n"
    "    materials: array of strings,\n"
    "    differentiation: {\n"
    "      support_strategies: array of strings,\n"
    "      challenge_strategies: array of strings,\n"
    "      accommodations: array of strings (optional)\n"
    "    },\n"
    "    assessment: {\n"
    "      type: string (Formative/Summative/Diagnostic),\n"
    "      questions_or_tasks: array of strings,\n"
    "      rubric: object or string,\n"
    "      duration_minutes: number\n"
    "    },\n"
    "    homework: {\n"
    "      tasks: array of strings,\n"
    "      estimated_time_minutes: number,\n"
    "      due_date_offset_days: number\n"
    "    },\n"
    "    sections: array of objects [{\n"
    "      section_number: number,\n"
    "      title: string,\n"
    "      activities: array of strings,\n"
    "      materials: array of strings,\n"
    "      assessment: string\n"
    "    }] (length exactly sections_per_week)\n"
    "  }]\n"
    
    "- supplementary_resources (array of objects): [{\n"
    "    title: string,\n"
    "    url: string,\n"
    "    type: string (video/article/simulation/dataset),\n"
    "    duration_minutes: number (optional),\n"
    "    description: string (optional),\n"
    "    grade_appropriate: boolean (optional)\n"
    "  }]\n"
    
    "- quality_checklist (object): {\n"
    "    realistic_timing: boolean,\n"
    "    diverse_activities: boolean,\n"
    "    clear_assessments: boolean,\n"
    "    differentiation_included: boolean,\n"
    "    standards_aligned: boolean\n"
    "  }\n\n"
    
    "CONSTRAINTS:\n"
    "- Use ONLY double quotes for strings\n"
    "- Keep descriptions concise but informative (50-200 words)\n"
    "- Ensure all URLs are valid and accessible\n"
    "- Timeline entries must be realistic (total should match lecture duration)\n"
    "- Each week must have exactly {sections_per_week} sections\n"
    "- Assessment rubrics should be specific and measurable\n"
    "- Do NOT include prose, explanations, code fences, or markdown\n"
    "- Return ONLY a single valid JSON object\n"
)

            raw = chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": combined_text}
                ],
                temperature=0.4,
                max_tokens=8000
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

