import os
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "agents" / "prompts"


def test_prompt_files_exist():
    files = [
        "orchestra.md",
        "lesson_plan.md",
        "assessment.md",
        "timetable.md",
        "email.md",
    ]
    for fname in files:
        p = PROMPTS_DIR / fname
        assert p.exists(), f"Missing prompt file: {p}"
        content = p.read_text(encoding="utf-8").strip()
        assert len(content) > 50, f"Prompt file too short: {p}"


def test_orchestra_prompt_has_delegate_marker():
    p = PROMPTS_DIR / "orchestra.md"
    text = p.read_text(encoding="utf-8").lower()
    assert "delegate:" in text, "orchestra prompt should mention 'delegate:' convention"


def test_specialist_prompts_reference_json():
    for name in ("lesson_plan.md", "assessment.md", "timetable.md", "email.md"):
        p = PROMPTS_DIR / name
        text = p.read_text(encoding="utf-8").lower()
        assert "json" in text, f"{name} should mention JSON output"
