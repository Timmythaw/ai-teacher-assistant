"""
AutoGen agent definitions (no business logic).

Creates per-role AutoGen agents (orchestra/planner, specialists, user proxy)
and registers existing project tools from core.autogen.tools_registry so the
planner and specialists can invoke them via function-calling.

Manager (GroupChat) wiring is provided separately in agents/autogen_manager.py.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.autogen.model_config import get_autogen_llm_config
from core.autogen.tools_registry import get_tools_for_role, run_tool, ToolSpec
from core.logger import logger

try:
    from autogen import AssistantAgent, UserProxyAgent, register_function
except Exception as e:
    # Defer import errors to runtime usage; helps with static analysis
    AssistantAgent = None  # type: ignore
    UserProxyAgent = None  # type: ignore
    register_function = None  # type: ignore
    logger.warning("AutoGen not available: %s", e)


PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str, fallback: str) -> str:
    p = PROMPTS_DIR / f"{name}.md"
    try:
        if p.exists():
            return p.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed reading prompt %s: %s", p, e)
    return fallback


def _make_agent(role: str, system_prompt: str):
    llm_cfg = get_autogen_llm_config(role)
    if AssistantAgent is None:
        raise RuntimeError("AutoGen AssistantAgent unavailable")
    return AssistantAgent(
        name=role,
        system_message=system_prompt,
        llm_config=llm_cfg,
    )


def _make_user_proxy(human_input_mode: str = "NEVER"):
    # UserProxy executes tools and can optionally ask for human input
    if UserProxyAgent is None:
        raise RuntimeError("AutoGen UserProxyAgent unavailable")
    return UserProxyAgent(
        name="user",
        human_input_mode=human_input_mode,
    )


def create_agents(human_input_mode: str = "NEVER") -> Dict[str, Any]:
    """Create AutoGen agents with role prompts and llm settings."""
    orchestra_prompt = _load_prompt(
        "orchestra",
        fallback=(
            "You are the planner/orchestrator.\n"
            "- Understand the teacher's request, outline a short plan, and annotate checkpoints.\n"
            "- When delegating work, include a line starting with: 'delegate: <lesson|assessment|timetable|email>'.\n"
            "- Prefer calling tools; avoid long free-form answers.\n"
            "- Ask for missing files succinctly."
        ),
    )
    lesson_prompt = _load_prompt(
        "lesson_plan",
        fallback=(
            "You design concise, structured lesson plans. Return JSON the renderer expects."
        ),
    )
    assessment_prompt = _load_prompt(
        "assessment",
        fallback=(
            "You design assessments. Return valid JSON with title, type, difficulty, questions[], rubric[]."
        ),
    )
    timetable_prompt = _load_prompt(
        "timetable",
        fallback=(
            "You suggest consistent weekly timetables respecting constraints. Output suggested_slots[]."
        ),
    )
    email_prompt = _load_prompt(
        "email",
        fallback=(
            "You draft short, clear emails. Prefer JSON {subject, body}."
        ),
    )

    user = _make_user_proxy(human_input_mode=human_input_mode)
    orchestra = _make_agent("orchestra", orchestra_prompt)
    lesson = _make_agent("lesson", lesson_prompt)
    assessment = _make_agent("assessment", assessment_prompt)
    timetable = _make_agent("timetable", timetable_prompt)
    email = _make_agent("email", email_prompt)

    return {
        "user": user,
        "orchestra": orchestra,
        "lesson": lesson,
        "assessment": assessment,
        "timetable": timetable,
        "email": email,
    }


def _register_one(tool: ToolSpec, callers: List[Any], executor: Any):
    """Register a single tool into AutoGen with dynamic wrapper."""
    if register_function is None:
        raise RuntimeError("AutoGen register_function unavailable")

    # Create a thin wrapper preserving the tool name and doc for LLM visibility.
    def _wrapper(input: Dict[str, Any]) -> Any:  # noqa: ANN001 - signature exposed to LLM
        """AutoGen tool wrapper."""
        res = run_tool(tool.name, input)
        if not res.get("ok"):
            # Return a structured error so the LLM can decide to retry or ask for help
            return {"error": res.get("error"), "tool": tool.name}
        return res.get("result")

    _wrapper.__name__ = tool.name  # help autogen show function name
    _wrapper.__doc__ = f"{tool.description}\nInput schema: {tool.input_schema}"

    # Decorate with AutoGen registration for the provided callers and executor
    decorated = register_function(caller=callers, executor=executor, description=tool.description)(_wrapper)
    return decorated


def register_registry_tools(agents: Dict[str, Any]) -> None:
    """Register tools from the registry for orchestra and allowed specialists."""
    orchestra = agents["orchestra"]
    user = agents["user"]
    # Specialists available in this build
    specialists = {k: v for k, v in agents.items() if k in ("lesson", "assessment", "timetable", "email")}

    # Collect per-role tool sets
    # We register each tool once, but allow multiple callers: orchestra + specific specialists.
    # This ensures the planner can call everything, while specialists call only their allowed tools.
    role_callers: Dict[str, List[Any]] = {
        "orchestra": [orchestra],
        "lesson": [specialists.get("lesson")] if specialists.get("lesson") else [],
        "assessment": [specialists.get("assessment")] if specialists.get("assessment") else [],
        "timetable": [specialists.get("timetable")] if specialists.get("timetable") else [],
        "email": [specialists.get("email")] if specialists.get("email") else [],
    }

    # Iterate over all tools and register with appropriate callers
    # We determine allowed callers by intersecting tool.roles with available agents
    from core.autogen.tools_registry import get_tool_registry

    for name, spec in get_tool_registry().items():
        callers: List[Any] = []
        # Always include orchestra
        callers.extend(role_callers.get("orchestra", []))
        # Add any specialist allowed by the tool and present in agents
        for r in spec.roles:
            if r == "orchestra":
                continue
            agent_obj = specialists.get(r)
            if agent_obj is not None:
                callers.append(agent_obj)
        # Remove None values just in case
        callers = [c for c in callers if c is not None]
        if not callers:
            continue
        _register_one(spec, callers, executor=user)


__all__ = [
    "create_agents",
    "register_registry_tools",
]
