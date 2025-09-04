"""
AutoGen Tools Registry

Bridges existing business tools (lesson/assessment/timetable/email, renderers,
calendar/form integrations) into a single registry consumable by AutoGen agents
and by the legacy Orchestrator if desired.

Each tool entry provides:
- name: action string
- func: callable taking a single dict input and returning any
- validator: optional callable that returns bool for output validation
- description: short human-friendly purpose
- input_schema: string hint (name) for the expected input shape
- roles: which AutoGen roles are allowed to invoke it (e.g., ["orchestra", "lesson"]) 

Helpers are provided to fetch tools per role and to run+validate a tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.logger import logger


# --- Lazy agent accessors to avoid heavy imports at module import time ---

_lesson_agent = None
_assessment_agent = None
_timetable_agent = None
_email_agent = None


def _get_lesson_agent():
    global _lesson_agent
    if _lesson_agent is None:
        from agents.lesson_plan_agent import LessonPlanAgent
        _lesson_agent = LessonPlanAgent()
    return _lesson_agent


def _get_assessment_agent():
    global _assessment_agent
    if _assessment_agent is None:
        from agents.assessment_agent import AssessmentAgent
        _assessment_agent = AssessmentAgent()
    return _assessment_agent


def _get_timetable_agent():
    global _timetable_agent
    if _timetable_agent is None:
        from agents.timetable_agent import TimetableAgent
        _timetable_agent = TimetableAgent()
    return _timetable_agent


def _get_email_agent():
    global _email_agent
    if _email_agent is None:
        try:
            from agents.email_agent import EmailAgent  # type: ignore
            _email_agent = EmailAgent()
        except Exception as e:
            logger.warning("EmailAgent unavailable: %s", e)
            _email_agent = None
    return _email_agent


# --- Validators (mirror orchestration defaults) ---

def _v_markdown(md: Any) -> bool:
    return isinstance(md, str) and md.strip() != ""


def _v_lesson(plan: Any) -> bool:
    if not isinstance(plan, dict):
        return False
    weekly = plan.get("weekly_schedule") or plan.get("weekly") or []
    dw = plan.get("duration_weeks") or plan.get("total_duration")
    spw = plan.get("sections_per_week")
    return bool(isinstance(weekly, list) and len(weekly) > 0 and isinstance(spw, int) and isinstance(dw, int))


def _v_assessment(a: Any) -> bool:
    return isinstance(a, dict) and isinstance(a.get("questions"), list) and len(a["questions"]) > 0


def _v_form(res: Any) -> bool:
    if not isinstance(res, dict):
        return False
    if not bool(res.get("success")):
        return False
    return bool(res.get("formId") or res.get("formUrl"))


def _v_timetable(tt: Any) -> bool:
    if not isinstance(tt, dict):
        return False
    slots = tt.get("suggested_slots")
    return isinstance(slots, list) and all(isinstance(x, dict) and x.get("start") and x.get("end") and x.get("title") for x in slots)


def _v_sched(res: Any) -> bool:
    return isinstance(res, (list, dict))


def _v_email_draft(d: Any) -> bool:
    return isinstance(d, dict) and (d.get("subject") is not None or d.get("ok") in (True, False))


def _v_email_send(d: Any) -> bool:
    return isinstance(d, dict) and (d.get("ok") in (True, False))


# --- Tool wrappers using existing business logic ---


def _t_generate_lesson_plan(inp: Dict[str, Any]) -> Dict[str, Any]:
    ag = _get_lesson_agent()
    sources = inp.get("sources") or {}
    dw = int(inp.get("duration_weeks") or inp.get("total_duration") or 8)
    cs = int(inp.get("class_size") or 30)
    spw = int(inp.get("sections_per_week") or 1)
    return ag.generate_plan(sources, dw, cs, spw)


def _t_render_lesson_markdown(inp: Dict[str, Any]) -> str:
    from core.md_render import render_lesson_plan_markdown
    return render_lesson_plan_markdown(inp.get("plan") or {})


def _t_suggest_timetable(inp: Dict[str, Any]) -> Dict[str, Any]:
    ag = _get_timetable_agent()
    plan = inp.get("plan") or {}
    slot_hours = int(inp.get("slot_hours", 1))
    work_hours = inp.get("work_hours", (9, 17))
    if isinstance(work_hours, list):
        work_hours = tuple(work_hours)
    calendar_id = inp.get("calendar_id", "primary")
    location_hint = inp.get("location_hint")
    attendees = inp.get("attendees")
    return ag.suggest_consistent_schedule(
        plan_or_pdf=plan,
        slot_hours=slot_hours,
        work_hours=work_hours,  # type: ignore[arg-type]
        calendar_id=calendar_id,
        location_hint=location_hint,
        attendees=attendees,
    )


def _t_schedule_calendar(inp: Dict[str, Any]):
    from integrations.calendar_orchestrator import schedule_from_timetable
    return schedule_from_timetable(inp.get("timetable") or {})


def _t_generate_assessment(inp: Dict[str, Any]) -> Dict[str, Any]:
    ag = _get_assessment_agent()
    src = str(inp.get("source") or "")
    spec = inp.get("spec") or {}
    return ag.generate_assessment(src, spec)


def _t_render_assessment_markdown(inp: Dict[str, Any]) -> str:
    from core.md_render import render_assessment_markdown
    return render_assessment_markdown(inp.get("assessment") or {})


def _t_create_google_form(inp: Dict[str, Any]) -> Dict[str, Any]:
    from integrations.form_creator import create_google_form
    assessment = inp.get("assessment") or {}
    title = inp.get("title") or assessment.get("title") or "Assessment"
    return create_google_form(assessment, title=title)


def _t_email_draft(inp: Dict[str, Any]) -> Dict[str, Any]:
    ag = _get_email_agent()
    prompt = inp.get("prompt") or ""
    if ag and hasattr(ag, "run"):
        return ag.run(prompt)
    return {"ok": False, "error": "Email agent unavailable"}


def _t_email_send(inp: Dict[str, Any]) -> Dict[str, Any]:
    ag = _get_email_agent()
    prompt = inp.get("prompt") or ""
    if ag and hasattr(ag, "run"):
        return ag.run(prompt)
    return {"ok": False, "error": "Email agent unavailable"}


@dataclass
class ToolSpec:
    name: str
    func: Callable[[Dict[str, Any]], Any]
    validator: Optional[Callable[[Any], bool]]
    description: str
    input_schema: str
    roles: List[str]


def build_registry() -> Dict[str, ToolSpec]:
    """Assemble the tool registry mapping action -> ToolSpec."""
    tools: Dict[str, ToolSpec] = {}

    def reg(t: ToolSpec):
        tools[t.name] = t

    reg(ToolSpec(
        name="generate_lesson_plan",
        func=_t_generate_lesson_plan,
        validator=_v_lesson,
        description="Generate a structured lesson plan from provided sources and parameters.",
        input_schema="lesson_input",
        roles=["orchestra", "lesson"],
    ))

    reg(ToolSpec(
        name="render_lesson_markdown",
        func=_t_render_lesson_markdown,
        validator=_v_markdown,
        description="Render lesson plan JSON into Markdown for display.",
        input_schema="{ plan }",
        roles=["orchestra", "lesson"],
    ))

    reg(ToolSpec(
        name="suggest_timetable",
        func=_t_suggest_timetable,
        validator=_v_timetable,
        description="Suggest a consistent weekly timetable from a plan or PDF.",
        input_schema="{ plan | pdf_path, slot_hours?, work_hours?, calendar_id?, location_hint? }",
        roles=["orchestra", "timetable", "lesson"],
    ))

    reg(ToolSpec(
        name="schedule_calendar",
        func=_t_schedule_calendar,
        validator=_v_sched,
        description="Create Google Calendar events from suggested timetable slots.",
        input_schema="{ timetable }",
        roles=["orchestra", "timetable"],
    ))

    reg(ToolSpec(
        name="generate_assessment",
        func=_t_generate_assessment,
        validator=_v_assessment,
        description="Generate an assessment (questions, rubric) from material and options.",
        input_schema="assessment_input",
        roles=["orchestra", "assessment"],
    ))

    reg(ToolSpec(
        name="render_assessment_markdown",
        func=_t_render_assessment_markdown,
        validator=_v_markdown,
        description="Render assessment JSON into Markdown for display.",
        input_schema="{ assessment }",
        roles=["orchestra", "assessment"],
    ))

    reg(ToolSpec(
        name="create_google_form",
        func=_t_create_google_form,
        validator=_v_form,
        description="Create a Google Form from an assessment.",
        input_schema="{ assessment, title? }",
        roles=["orchestra", "assessment"],
    ))

    reg(ToolSpec(
        name="draft_email",
        func=_t_email_draft,
        validator=_v_email_draft,
        description="Draft an email given a prompt (subject/body).",
        input_schema="{ prompt }",
        roles=["orchestra", "email"],
    ))

    reg(ToolSpec(
        name="send_email",
        func=_t_email_send,
        validator=_v_email_send,
        description="Send or finalize an email based on a prompt.",
        input_schema="{ prompt }",
        roles=["orchestra", "email"],
    ))

    return tools


_REGISTRY: Optional[Dict[str, ToolSpec]] = None


def get_tool_registry() -> Dict[str, ToolSpec]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_registry()
    return _REGISTRY


def get_tools_for_role(role: str) -> Dict[str, ToolSpec]:
    role = role.lower()
    return {name: spec for name, spec in get_tool_registry().items() if role in spec.roles}


def run_tool(name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run a tool by name and return { ok, result|error } with validator applied if available."""
    spec = get_tool_registry().get(name)
    if not spec:
        return {"ok": False, "error": f"No such tool: {name}"}
    try:
        out = spec.func(input_data or {})
        if spec.validator and not spec.validator(out):
            return {"ok": False, "error": f"Validation failed for {name}", "result": out}
        return {"ok": True, "result": out}
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e, exc_info=True)
        return {"ok": False, "error": str(e)}


__all__ = [
    "ToolSpec",
    "get_tool_registry",
    "get_tools_for_role",
    "run_tool",
]
