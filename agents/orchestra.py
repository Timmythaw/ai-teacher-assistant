import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.logger import logger


def validate_json_schema(output_str: Any, schema_keys: List[str]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Backward-compatible validator used in notebooks/tests.
    Accepts a JSON string or dict, ensures required top-level keys.
    Returns (ok, data_dict_or_none).
    """
    raw = output_str
    try:
        if isinstance(output_str, str):
            data = json.loads(output_str)
        elif isinstance(output_str, dict):
            data = output_str
        else:
            return False, None
        for key in schema_keys:
            if key not in data:
                return False, None
        return True, data
    except Exception:
        return False, None


class Orchestrator:
    """
    A conductor for multi-step jobs:
    - Plan: break a high-level request into tasks
    - Route: run each task via registered tools
    - Verify: validate outputs with per-action validators
    - Recover: retry AI-dependent steps
    - Track: keep per-job state with structured logs
    - HIL: pause at checkpoints for approval
    """

    def __init__(self, model: str = "openai/gpt-5-chat-latest", max_retries: int = 2):
        self.model = model
        self.max_retries = max_retries
        self.tools: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self.validators: Dict[str, Callable[[Any], bool]] = {}

    # -------- Registry --------

    def register(self, action: str, func: Callable[[Dict[str, Any]], Any], validator: Optional[Callable[[Any], bool]] = None):
        self.tools[action] = func
        if validator:
            self.validators[action] = validator

    def _safe_init_email_agent(self) -> bool:
        try:
            from agents.email_agent import EmailAgent  # noqa: F401
            return True
        except Exception:
            return False

    def register_defaults(self):
        """
        Lazily import and register common project tools with validators.
        Call this once at app start.
        """
        try:
            from agents.lesson_plan_agent import LessonPlanAgent
            from agents.assessment_agent import AssessmentAgent
            from agents.timetable_agent import TimetableAgent
            from core.md_render import render_lesson_plan_markdown, render_assessment_markdown
            from integrations.calendar_orchestrator import schedule_from_timetable
            from integrations.form_creator import create_google_form
            if self._safe_init_email_agent():
                from agents.email_agent import EmailAgent
            else:
                EmailAgent = None  # type: ignore
        except Exception as e:
            logger.error("register_defaults import error: %s", e)
            return

        lp_agent = LessonPlanAgent(model=self.model)
        asmt_agent = AssessmentAgent()
        tt_agent = TimetableAgent()
        email_agent = EmailAgent() if 'EmailAgent' in locals() and EmailAgent else None

        def _gen_lesson_plan(inp: Dict[str, Any]) -> Dict[str, Any]:
            sources = inp.get("sources") or {}
            dw = int(inp.get("duration_weeks") or inp.get("total_duration") or 8)
            cs = int(inp.get("class_size") or 30)
            spw = int(inp.get("sections_per_week") or 1)
            return lp_agent.generate_plan(sources, dw, cs, spw)

        def _render_lp_md(inp: Dict[str, Any]) -> str:
            return render_lesson_plan_markdown(inp.get("plan") or {})

        def _suggest_timetable(inp: Dict[str, Any]) -> Dict[str, Any]:
            plan = inp.get("plan") or {}
            slot_hours = int(inp.get("slot_hours", 1))
            work_hours = tuple(inp.get("work_hours", (9, 17)))
            calendar_id = inp.get("calendar_id", "primary")
            location_hint = inp.get("location_hint")
            return tt_agent.suggest_consistent_schedule(
                plan_or_pdf=plan,
                slot_hours=slot_hours,
                work_hours=work_hours,  # type: ignore[arg-type]
                calendar_id=calendar_id,
                location_hint=location_hint,
            )

        def _schedule_calendar(inp: Dict[str, Any]):
            return schedule_from_timetable(inp.get("timetable") or {})

        def _gen_assessment(inp: Dict[str, Any]) -> Dict[str, Any]:
            src = str(inp.get("source") or "")
            spec = inp.get("spec") or {}
            return asmt_agent.generate_assessment(src, spec)

        def _render_asmt_md(inp: Dict[str, Any]) -> str:
            return render_assessment_markdown(inp.get("assessment") or {})

        def _create_form(inp: Dict[str, Any]) -> Dict[str, Any]:
            asmt = inp.get("assessment") or {}
            title = inp.get("title") or asmt.get("title") or "Assessment"
            return create_google_form(asmt, title=title)

        def _draft_email(inp: Dict[str, Any]) -> Dict[str, Any]:
            # Fallback: re-use run() in draft mode via a prompt flag
            prompt = inp.get("prompt") or ""
            if email_agent and hasattr(email_agent, "run"):
                return email_agent.run(prompt)
            return {"ok": False, "error": "Email agent unavailable"}

        def _send_email(inp: Dict[str, Any]) -> Dict[str, Any]:
            prompt = inp.get("prompt") or ""
            if email_agent and hasattr(email_agent, "run"):
                return email_agent.run(prompt)
            return {"ok": False, "error": "Email agent unavailable"}

        # Validators
        def v_lp(plan: Any) -> bool:
            if not isinstance(plan, dict):
                return False
            weekly = plan.get("weekly_schedule") or plan.get("weekly") or []
            dw = plan.get("duration_weeks") or plan.get("total_duration")
            spw = plan.get("sections_per_week")
            return bool(isinstance(weekly, list) and len(weekly) > 0 and isinstance(spw, int) and isinstance(dw, int))

        def v_md(md: Any) -> bool:
            return isinstance(md, str) and md.strip() != ""

        def v_asmt(a: Any) -> bool:
            return isinstance(a, dict) and isinstance(a.get("questions"), list) and len(a["questions"]) > 0

        def v_form(res: Any) -> bool:
            if not isinstance(res, dict):
                return False
            if not bool(res.get("success")):
                return False
            return bool(res.get("formId") or res.get("formUrl"))

        def v_tt(tt: Any) -> bool:
            if not isinstance(tt, dict):
                return False
            slots = tt.get("suggested_slots")
            return isinstance(slots, list) and all(isinstance(x, dict) and x.get("start") and x.get("end") and x.get("title") for x in slots)

        def v_sched(res: Any) -> bool:
            return isinstance(res, (list, dict))

        def v_email_draft(d: Any) -> bool:
            return isinstance(d, dict) and (d.get("subject") is not None)

        def v_email_send(d: Any) -> bool:
            return isinstance(d, dict) and (d.get("ok") in (True, False))

        # Register
        self.register("generate_lesson_plan", _gen_lesson_plan, v_lp)
        self.register("render_lesson_markdown", _render_lp_md, v_md)
        self.register("suggest_timetable", _suggest_timetable, v_tt)
        self.register("schedule_calendar", _schedule_calendar, v_sched)
        self.register("generate_assessment", _gen_assessment, v_asmt)
        self.register("render_assessment_markdown", _render_asmt_md, v_md)
        self.register("create_google_form", _create_form, v_form)
        if email_agent:
            self.register("draft_email", _draft_email, v_email_draft)
            self.register("send_email", _send_email, v_email_send)

    # -------- Planning --------

    def plan(self, teacher_request: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = options or {}
        job_id = str(uuid.uuid4())
        tasks: List[Dict[str, Any]] = []
        checkpoints: List[str] = []

        req = (teacher_request or "").lower()
        seq = 1

        def _tid() -> str:
            nonlocal seq
            tid = f"t{seq}"
            seq += 1
            return tid

        # Lesson flow
        if any(k in req for k in ["lesson", "plan", "weekly", "syllabus"]):
            t1 = {"id": _tid(), "action": "generate_lesson_plan", "input": options.get("lesson_input", {}), "depends_on": [], "status": "pending"}
            t2 = {"id": _tid(), "action": "render_lesson_markdown", "input": {"plan": f"${t1['id']}.result"}, "depends_on": [t1["id"]], "status": "pending"}
            t3 = {"id": _tid(), "action": "suggest_timetable", "input": {"plan": f"${t1['id']}.result", **options.get("timetable_opts", {})}, "depends_on": [t1["id"]], "status": "pending"}
            t4 = {"id": _tid(), "action": "schedule_calendar", "input": {"timetable": f"${t3['id']}.result"}, "depends_on": [t3["id"]], "status": "pending"}
            tasks += [t1, t2, t3, t4]
            checkpoints += [t1["id"], t3["id"]]

        # Assessment flow
        if any(k in req for k in ["assessment", "quiz", "exam", "test"]):
            a1 = {"id": _tid(), "action": "generate_assessment", "input": options.get("assessment_input", {}), "depends_on": [], "status": "pending"}
            a2 = {"id": _tid(), "action": "render_assessment_markdown", "input": {"assessment": f"${a1['id']}.result"}, "depends_on": [a1["id"]], "status": "pending"}
            a3 = {"id": _tid(), "action": "create_google_form", "input": {"assessment": f"${a1['id']}.result"}, "depends_on": [a1["id"]], "status": "pending"}
            tasks += [a1, a2, a3]
            checkpoints += [a1["id"]]

        # Email flow
        if "email" in req:
            e1 = {"id": _tid(), "action": "draft_email", "input": options.get("email_input", {}), "depends_on": [], "status": "pending"}
            e2 = {"id": _tid(), "action": "send_email", "input": options.get("email_input", {}), "depends_on": [e1["id"]], "status": "pending"}
            tasks += [e1, e2]
            checkpoints += [e1["id"]]

        # Default
        if not tasks:
            t1 = {"id": _tid(), "action": "generate_lesson_plan", "input": options.get("lesson_input", {}), "depends_on": [], "status": "pending"}
            t2 = {"id": _tid(), "action": "render_lesson_markdown", "input": {"plan": f"${t1['id']}.result"}, "depends_on": [t1["id"]], "status": "pending"}
            tasks += [t1, t2]
            checkpoints += [t1["id"]]

        return {
            "job_id": job_id,
            "request": teacher_request,
            "tasks": tasks,
            "checkpoints": checkpoints,
            "metadata": {"created_at": int(time.time())},
            "state": {"status": "pending"},
            "logs": [],
        }

    # -------- Execution --------

    def run(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        job = json.loads(json.dumps(plan))  # deep copy
        job["state"]["status"] = "running"
        tasks_by_id = {t["id"]: t for t in job["tasks"]}
        completed: Dict[str, Dict[str, Any]] = {}

        def _resolve_refs(val: Any) -> Any:
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                ref = val[2:-1]
                tid, _, attr = ref.partition(".")
                if tid in completed:
                    return completed[tid].get(attr)
                return None
            if isinstance(val, dict):
                return {k: _resolve_refs(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_resolve_refs(v) for v in val]
            return val

        remaining = set(tasks_by_id.keys())
        while remaining:
            progressed = False
            for tid in list(remaining):
                task = tasks_by_id[tid]
                if task["status"] not in ("pending", "failed"):
                    remaining.discard(tid)
                    continue
                deps = task.get("depends_on") or []
                if any(tasks_by_id[d]["status"] != "succeeded" for d in deps):
                    continue
                resolved_input = _resolve_refs(task.get("input") or {})
                out, err, attempts = self._run_task(task["action"], resolved_input)
                task["attempts"] = attempts
                if err:
                    task["status"] = "failed"
                    task["error"] = {"message": str(err)}
                    job["logs"].append({"ts": int(time.time()), "level": "error", "task_id": tid, "message": str(err)})
                else:
                    task["status"] = "succeeded"
                    task["result"] = out
                    job["logs"].append({"ts": int(time.time()), "level": "info", "task_id": tid, "message": "Task succeeded"})
                    completed[tid] = {"result": out}
                    if tid in (job.get("checkpoints") or []):
                        job["state"]["status"] = "paused"
                        job["state"]["wait_for"] = tid
                        return job
                remaining.discard(tid)
                progressed = True
            if not progressed:
                job["state"]["status"] = "failed"
                job["logs"].append({"ts": int(time.time()), "level": "error", "message": "Execution stalled. Check dependencies/errors."})
                return job

        job["state"]["status"] = "succeeded"
        return job

    def _run_task(self, action: str, inp: Dict[str, Any]) -> Tuple[Optional[Any], Optional[Exception], int]:
        func = self.tools.get(action)
        if not func:
            return None, Exception(f"No tool registered for action '{action}'"), 0

        retryable = action in {"generate_lesson_plan", "generate_assessment", "draft_email"}
        attempts = 0
        last_err: Optional[Exception] = None

        while True:
            attempts += 1
            try:
                out = func(inp or {})
                validator = self.validators.get(action)
                if validator and not validator(out):
                    raise Exception(f"Validation failed for {action}")
                return out, None, attempts
            except Exception as e:
                last_err = e
                logger.error("Task %s failed (attempt %s): %s", action, attempts, e)
                if not retryable or attempts > self.max_retries:
                    return None, last_err, attempts
                time.sleep(0.7 * attempts)

    # -------- Legacy helpers --------

    def execute(self, tasks: List[Dict[str, Any]], agents: Dict[str, Any] | None = None) -> Dict[str, Any]:
        plan = {
            "job_id": str(uuid.uuid4()),
            "request": "(adhoc)",
            "tasks": tasks,
            "checkpoints": [],
            "metadata": {"created_at": int(time.time())},
            "state": {"status": "pending"},
            "logs": [],
        }
        return self.run(plan)

    def reflect(self, results: Dict[str, Any]) -> Dict[str, Any]:
        tasks = results.get("tasks", [])
        return {
            "status": results.get("state", {}).get("status"),
            "succeeded": [t["id"] for t in tasks if t.get("status") == "succeeded"],
            "failed": [t["id"] for t in tasks if t.get("status") == "failed"],
            "paused_after": results.get("state", {}).get("wait_for"),
        }