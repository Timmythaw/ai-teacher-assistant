"""
Speaker selection policy for the AutoGen orchestration layer.

Rules:
- Start with orchestra as the initial speaker.
- When orchestra messages include "delegate: <agent>", hand off to that specialist.
- After any specialist replies, pause for user confirmation (human-in-the-loop).
- When the user replies, return control to the orchestra to plan next.

This module is framework-agnostic; it does not import AutoGen directly.
The manager can call decide_next(...) with the last speaker and message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


ORCHESTRA = "orchestra"
USER = "user"
SPECIALISTS = ["lesson", "assessment", "timetable", "email"]


ALIASES = {
    # Core
    "planner": ORCHESTRA,
    "orchestrator": ORCHESTRA,
    "orchestra": ORCHESTRA,
    # Lesson
    "lesson": "lesson",
    "lesson_plan": "lesson",
    "lesson-plan": "lesson",
    "lesson_plan_agent": "lesson",
    # Assessment
    "assessment": "assessment",
    "quiz": "assessment",
    "exam": "assessment",
    "test": "assessment",
    "mcq": "assessment",
    "multiple choice": "assessment",
    "assessment_agent": "assessment",
    # Timetable/Calendar
    "timetable": "timetable",
    "schedule": "timetable",
    "calendar": "timetable",
    "timetable_agent": "timetable",
    # Email
    "email": "email",
    "gmail": "email",
    "email_agent": "email",
}


@dataclass
class Decision:
    next_speaker: str
    pause: bool
    reason: str


def normalize_role(name: str) -> Optional[str]:
    key = (name or "").strip().lower()
    return ALIASES.get(key)


def parse_delegation(text: str, available_roles: Iterable[str]) -> Optional[str]:
    """Find 'delegate: <role>' marker and map to a normalized available role."""
    if not text:
        return None
    m = re.search(r"delegate\s*:\s*([a-zA-Z0-9_\- ]{2,40})", text, re.IGNORECASE)
    if not m:
        return None
    raw = m.group(1).strip().lower()
    # try direct hit
    candidates = [raw]
    # split on spaces/hyphens/underscores and join variations
    parts = re.split(r"[\s_\-]+", raw)
    if parts and len(parts) > 1:
        candidates.append("_".join(parts))
        candidates.append("-".join(parts))
        candidates.append(parts[0])
    # map via aliases and verify availability
    normalized: List[str] = []
    for c in candidates:
        role = normalize_role(c)
        if role and role not in normalized:
            normalized.append(role)
    avail = {r.lower() for r in available_roles}
    for role in normalized:
        if role in avail:
            return role
    return None


def _looks_like_user_request_needed(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    # Heuristics: orchestra is asking for files/confirmation/clarification
    trigger_words = [
        "attach", "upload", "provide", "supply", "missing",
        "please confirm", "confirm", "approval", "approve",
        "clarify", "clarification", "more info", "need", "required",
        "file", "pdf", "document",
    ]
    if any(w in t for w in trigger_words):
        return True
    # Any explicit question may imply user input
    if "?" in t:
        return True
    return False


def initial_speaker() -> str:
    return ORCHESTRA


def decide_next(last_speaker: Optional[str], last_message: Optional[str], *,
                available_roles: Iterable[str] = (ORCHESTRA, USER, *SPECIALISTS)) -> Decision:
    """
    Decide the next speaker and whether to pause for human confirmation.

    - If user just spoke -> orchestra plans next (no pause).
    - If orchestra spoke and included 'delegate: X' -> X speaks next (no pause).
    - If orchestra spoke but needs user input -> user next (pause).
    - If a specialist spoke -> user next (pause for approval).
    - Fallback -> orchestra.
    """
    roles = {r.lower() for r in available_roles}
    last = (last_speaker or "").lower()
    msg = last_message or ""

    if last == USER:
        # User provided input; orchestra should plan next.
        return Decision(next_speaker=ORCHESTRA if ORCHESTRA in roles else USER, pause=False, reason="user->orchestra")

    if last == ORCHESTRA:
        # Check for explicit delegation
        target = parse_delegation(msg, roles)
        if target and target in roles and target != USER:
            return Decision(next_speaker=target, pause=False, reason=f"orchestra delegated to {target}")
        # Otherwise, if asking for input/confirmation, hand to user and pause
        if _looks_like_user_request_needed(msg) and USER in roles:
            return Decision(next_speaker=USER, pause=True, reason="orchestra requests user input")
        # Default: keep control with orchestra (e.g., planning/summary)
        return Decision(next_speaker=ORCHESTRA, pause=False, reason="orchestra continues")

    if last in SPECIALISTS and last in roles:
        # After any specialist reply, pause for user approval.
        if USER in roles:
            return Decision(next_speaker=USER, pause=True, reason=f"specialist {last} completed; awaiting approval")
        return Decision(next_speaker=ORCHESTRA, pause=True, reason="specialist completed; no user role available")

    # Unknown or first turn -> orchestra starts
    return Decision(next_speaker=ORCHESTRA if ORCHESTRA in roles else USER, pause=False, reason="default")


__all__ = [
    "Decision",
    "ORCHESTRA",
    "USER",
    "SPECIALISTS",
    "normalize_role",
    "parse_delegation",
    "initial_speaker",
    "decide_next",
]
