import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from core.ai_client import chat_completion
from core.pdf_tool import extract_text_from_pdf
from core.logger import logger

class AssessmentAgent:
    gpt_model = os.getenv("GPT_MODEL", "openai/gpt-5-chat-latest")
    def __init__(self, model=gpt_model):
        self.model = model

    def generate_assessment(self, course_material: str, options: dict) -> dict:
        try:
            logger.info("AssessmentAgent started with inputs: %s", options)
            # PDF or raw text
            if course_material.endswith(".pdf"):
                material_text = extract_text_from_pdf(course_material)
                logger.info("Extracted text from PDF: %s (length=%d)", course_material, len(material_text))
            else:
                material_text = course_material
                logger.info("Received raw text input (length=%d)", len(material_text))

            if not material_text.strip():
                logger.warning("No valid course material found in %s", course_material)
                return {"error": "No valid course material found."}

            system_prompt = (
                "You are an assessment designer.\n"
                "Create an assessment based on provided material.\n\n"
                "Return ONLY a valid JSON object with these keys: \n"
                "- title (string)\n"
                "- type (MCQ | ShortAnswer | Project)\n"
                "- difficulty (string)\n"
                "- questions (array of objects with: q, options(if MCQ), answer)\n"
                "- rubric (array of objects with: criteria, points) if rubric requested\n\n"
                "Do not include any prose, explanations, code fences, or markdown.\n"
                "Use only double quotes."
            )

            user_prompt = (
                f"Create a {options.get('type', 'MCQ')} assessment.\n"
                f"Difficulty: {options.get('difficulty', 'Medium')}.\n"
                f"Number of questions: {options.get('count', 5)}.\n"
                f"Include rubric: {options.get('rubric', True)}.\n"
            )

            raw = chat_completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": material_text},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4,
                max_tokens=1800
            )
            print(raw)
            # Try strict JSON parse first, then attempt sanitization
            parsed = None
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                # Attempt to extract a JSON block from code fences
                fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw)
                candidate = fence_match.group(1) if fence_match else None
                if not candidate:
                    # Fallback: take substring from first '{' to last '}'
                    start = raw.find('{')
                    end = raw.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        candidate = raw[start:end+1]
                if candidate:
                    # Light normalization: remove trailing commas before } or ] and normalize smart quotes
                    norm = candidate
                    norm = norm.replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'")
                    norm = re.sub(r",\s*([}\]])", r"\1", norm)
                    try:
                        parsed = json.loads(norm)
                    except json.JSONDecodeError:
                        # Best-effort repair: balance braces/brackets by appending closers at end
                        def _balance_repair(s: str) -> str:
                            opens = []
                            out = []
                            in_str = False
                            esc = False
                            for ch in s:
                                out.append(ch)
                                if esc:
                                    esc = False
                                    continue
                                if ch == '\\':
                                    esc = True
                                    continue
                                if ch == '"' and not esc:
                                    in_str = not in_str
                                    continue
                                if in_str:
                                    continue
                                if ch in '{[':
                                    opens.append(ch)
                                elif ch in '}]':
                                    if opens and ((opens[-1] == '{' and ch == '}') or (opens[-1] == '[' and ch == ']')):
                                        opens.pop()
                                    else:
                                        # ignore unmatched closers
                                        pass
                            # append missing closers
                            closing = []
                            for op in reversed(opens):
                                closing.append('}' if op == '{' else ']')
                            return ''.join(out) + ''.join(closing)

                        repaired = _balance_repair(norm)
                        try:
                            parsed = json.loads(repaired)
                        except Exception:
                            # Last-resort salvage: extract fields by pattern and rebuild a minimal object
                            def _normalize(s: str) -> str:
                                return (
                                    s.replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'")
                                    .replace("\u2014", "-")
                                )
                            txt = _normalize(raw)
                            try:
                                import itertools
                                q_key = '"questions"'
                                q_idx = txt.find(q_key)
                                questions = []
                                if q_idx != -1:
                                    # find first '[' after key
                                    lb = txt.find('[', q_idx)
                                    if lb != -1:
                                        depth = 0
                                        arr_chars = []
                                        in_str = False
                                        esc = False
                                        for ch in txt[lb:]:
                                            arr_chars.append(ch)
                                            if esc:
                                                esc = False
                                                continue
                                            if ch == '\\':
                                                esc = True
                                                continue
                                            if ch == '"':
                                                in_str = not in_str
                                                continue
                                            if in_str:
                                                continue
                                            if ch == '[':
                                                depth += 1
                                            elif ch == ']':
                                                depth -= 1
                                                if depth == 0:
                                                    break
                                        arr_text = ''.join(arr_chars)
                                        # remove trailing commas in elements
                                        arr_text = re.sub(r",\s*([}\]])", r"\1", arr_text)
                                        try:
                                            questions = json.loads(arr_text)
                                        except Exception:
                                            questions = []
                                # Extract simple scalars
                                def _rx(key: str, default: str = "") -> str:
                                    m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', txt)
                                    return m.group(1) if m else default
                                title = _rx("title", "Assessment")
                                atype = _rx("type", options.get("type", "MCQ"))
                                diff = _rx("difficulty", options.get("difficulty", "Medium"))
                                if isinstance(questions, list) and questions:
                                    parsed = {
                                        "title": title,
                                        "type": atype,
                                        "difficulty": diff,
                                        "questions": questions,
                                    }
                                else:
                                    logger.error("Sanitized JSON still invalid. Raw: %s", raw)
                                    return {"error": "Model did not return valid JSON.", "raw": raw}
                            except Exception:
                                logger.error("Sanitized JSON still invalid. Raw: %s", raw)
                                return {"error": "Model did not return valid JSON.", "raw": raw}
                else:
                    logger.error("No JSON object could be extracted. Raw: %s", raw)
                    return {"error": "Model did not return valid JSON.", "raw": raw}

            # Ensure minimal structure
            if not isinstance(parsed, dict):
                logger.error("Parsed JSON is not an object. Parsed: %s", parsed)
                return {"error": "Model did not return a JSON object.", "raw": raw}

            parsed.setdefault("title", "Assessment")
            parsed.setdefault("type", options.get("type", "MCQ"))
            parsed.setdefault("difficulty", options.get("difficulty", "Medium"))
            parsed.setdefault("questions", [])
            if options.get("rubric", True):
                parsed.setdefault("rubric", [])

            logger.info(
                "AssessmentAgent successfully generated assessment with %d questions",
                len(parsed.get("questions", []))
            )
            return parsed
            
        except Exception as e:
            logger.error("AssessmentAgent failed: %s", e, exc_info=True)
            return {"error": f"AssessmentAgent failed: {e}"}

"""
asmt_agent = AssessmentAgent()
assessment = asmt_agent.generate_assessment(
    os.environ.get("LECTURE_PDF_PATH") ,
    {"type": "MCQ", "difficulty": "Medium", "count": 5, "rubric": True}
)
print(assessment)
"""