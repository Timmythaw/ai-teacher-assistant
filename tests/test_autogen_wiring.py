import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.autogen.tools_registry import get_tools_for_role, run_tool
from core.autogen.speaker_selection import decide_next, ORCHESTRA, USER


def test_tools_exposed_per_role_minimal():
    # Orchestra should see many tools
    orch_tools = get_tools_for_role("orchestra")
    assert "generate_lesson_plan" in orch_tools
    assert "generate_assessment" in orch_tools
    assert "suggest_timetable" in orch_tools
    assert "schedule_calendar" in orch_tools
    assert "create_google_form" in orch_tools

    # Lesson specialist should at least see lesson-specific tools
    lesson_tools = get_tools_for_role("lesson")
    assert "generate_lesson_plan" in lesson_tools
    assert "render_lesson_markdown" in lesson_tools

    # Assessment specialist should at least see assessment-specific tools
    assessment_tools = get_tools_for_role("assessment")
    assert "generate_assessment" in assessment_tools
    assert "render_assessment_markdown" in assessment_tools


def test_speaker_selection_delegation_and_pause():
    # Orchestra delegates to assessment -> next speaker assessment, no pause
    decision = decide_next(ORCHESTRA, "delegate: assessment", available_roles=[ORCHESTRA, "assessment", USER])
    assert decision.next_speaker == "assessment"
    assert decision.pause is False

    # Specialist replies -> user next, pause
    decision2 = decide_next("assessment", "Here is the draft assessment.", available_roles=[ORCHESTRA, "assessment", USER])
    assert decision2.next_speaker == USER
    assert decision2.pause is True

    # User replies -> orchestra next, no pause
    decision3 = decide_next(USER, "Looks good, continue.", available_roles=[ORCHESTRA, "assessment", USER])
    assert decision3.next_speaker == ORCHESTRA
    assert decision3.pause is False
