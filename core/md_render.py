from typing import Any, Dict, List, Optional, Iterable

def _as_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        import json
        return json.dumps(v, ensure_ascii=False)
    return str(v)

def _is_scalar(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool)) or v is None

def _humanize_key(k: str) -> str:
    if not k:
        return ""
    # split camelCase and snake_case into Title Case
    import re
    s = re.sub(r'(?<!^)(?=[A-Z])', ' ', k)
    s = s.replace("_", " ").strip()
    return s[:1].upper() + s[1:]

def _bullet_list(items: Optional[List[Any]], indent: int = 0) -> str:
    if not items:
        return ""
    pad = "  " * indent
    lines: List[str] = []
    for it in items:
        if isinstance(it, dict):
            lines.append(f"{pad}- " + ", ".join(f"{_humanize_key(k)}: {_as_str(v)}" for k, v in it.items()))
        elif isinstance(it, (list, tuple)):
            lines.append(f"{pad}- " + ", ".join(_as_str(x) for x in it))
        else:
            val = _as_str(it)
            if "\n" in val:
                # block under bullet
                first, *rest = val.splitlines()
                lines.append(f"{pad}- {first}")
                for r in rest:
                    lines.append(f"{pad}  {r}")
            else:
                lines.append(f"{pad}- {val}")
    return "\n".join(lines)

def _render_kv_block(d: Dict[str, Any], indent: int = 0, skip: Iterable[str] = ()) -> str:
    pad = "  " * indent
    lines: List[str] = []
    for k, v in d.items():
        if k in skip:
            continue
        label = _humanize_key(k)
        if _is_scalar(v):
            val = _as_str(v)
            if "\n" in val:
                lines.append(f"{pad}- {label}:")
                lines.append("\n".join(f"{pad}  {ln}" for ln in val.splitlines()))
            else:
                lines.append(f"{pad}- {label}: {val}")
        elif isinstance(v, list):
            lines.append(f"{pad}- {label}:")
            if v:
                lines.append(_bullet_list(v, indent=indent + 1))
        elif isinstance(v, dict):
            lines.append(f"{pad}- {label}:")
            nested = _render_kv_block(v, indent=indent + 1)
            if nested:
                lines.append(nested)
    return "\n".join([ln for ln in lines if ln.strip()])

def _render_list_of_entries(entries: List[Any], heading_prefix: str = "Item", start_index: int = 1) -> List[str]:
    out: List[str] = []
    for i, entry in enumerate(entries, start_index):
        if isinstance(entry, dict):
            title = entry.get("title") or entry.get("topic") or entry.get("name") or ""
            heading = f"### {heading_prefix} {i}{(': ' + str(title)) if title else ''}".rstrip()
            out.append(heading)
            out_block = _render_kv_block(entry)
            if out_block:
                out.append(out_block)
        else:
            out.append(f"### {heading_prefix} {i}")
            out.append(_as_str(entry))
    return out

def _looks_like_weeks(entries: List[Any]) -> bool:
    # Heuristic: dicts containing a "week" field
    return any(isinstance(e, dict) and ("week" in e or "Week" in e) for e in entries)

def render_lesson_plan_markdown(plan: Dict[str, Any]) -> str:
    if not isinstance(plan, dict):
        return "### Error\nInvalid lesson plan payload."
    if plan.get("error"):
        return f"### Error\n{_as_str(plan.get('error'))}"

    # Title
    title = _as_str(plan.get("title") or plan.get("name") or "Lesson Plan")
    out: List[str] = [f"# {title}"]

    # Classify top-level keys
    known_title_keys = {"title", "name"}
    weekly_keys = [
        "weekly_schedule", "weeks_plan", "weeks", "schedule",
        "modules", "units", "outline", "timeline"
    ]
    rendered_keys: set = set()

    # Meta (all top-level scalars except known containers and title)
    meta_items: List[str] = []
    for k, v in plan.items():
        if k in known_title_keys or k in weekly_keys:
            continue
        if _is_scalar(v):
            label = _humanize_key(k)
            meta_items.append(f"- {label}: {_as_str(v)}")
            rendered_keys.add(k)

    if meta_items:
        out.append("\n".join(meta_items))

    # Weekly-like containers, rendered with headings and all nested details
    for wk in weekly_keys:
        val = plan.get(wk)
        if isinstance(val, list) and val:
            section_title = _humanize_key(wk)
            out.append(f"\n## {section_title}")
            if _looks_like_weeks(val):
                # use 'Week N: <topic/title>' style headings
                for entry in val:
                    if isinstance(entry, dict):
                        wk_no = entry.get("week") or entry.get("Week") or entry.get("index") or entry.get("id")
                        topic = entry.get("topic") or entry.get("title") or entry.get("name") or ""
                        heading = f"### Week {wk_no}{(': ' + str(topic)) if topic else ''}".rstrip()
                        out.append(heading)
                        block = _render_kv_block(entry)
                        if block:
                            out.append(block)
                    else:
                        out.append(f"### Week entry")
                        out.append(_as_str(entry))
            else:
                out.extend(_render_list_of_entries(val, heading_prefix=section_title[:-1] if section_title.endswith('s') else section_title))
            rendered_keys.add(wk)
        elif isinstance(val, dict) and val:
            section_title = _humanize_key(wk)
            out.append(f"\n## {section_title}")
            block = _render_kv_block(val)
            if block:
                out.append(block)
            rendered_keys.add(wk)

    # Known rich sections that might exist (render if present and not rendered)
    rich_sections = [
        "objectives", "learning_objectives", "outcomes",
        "standards_alignment", "prerequisites",
        "resources", "external_resources",
        "assessments", "assessment_strategy",
        "activities", "materials", "notes"
    ]
    for rk in rich_sections:
        if rk in rendered_keys:
            continue
        val = plan.get(rk)
        if not val:
            continue
        section_title = _humanize_key(rk)
        out.append(f"\n## {section_title}")
        if _is_scalar(val):
            out.append(_as_str(val))
        elif isinstance(val, list):
            out.append(_bullet_list(val))
        elif isinstance(val, dict):
            block = _render_kv_block(val)
            if block:
                out.append(block)
        rendered_keys.add(rk)

    # Render any remaining dict/list top-level fields to avoid losing information
    for k, v in plan.items():
        if k in rendered_keys or k in known_title_keys or k in weekly_keys:
            continue
        if not v:
            continue
        section_title = _humanize_key(k)
        out.append(f"\n## {section_title}")
        if _is_scalar(v):
            out.append(_as_str(v))
        elif isinstance(v, list):
            out.append(_bullet_list(v))
        elif isinstance(v, dict):
            block = _render_kv_block(v)
            if block:
                out.append(block)
        rendered_keys.add(k)

    content = "\n\n".join(s for s in out if s is not None and str(s).strip())
    return content.strip() or "# Lesson Plan\n_No content_"

def render_assessment_markdown(assessment: Dict[str, Any]) -> str:
    if not isinstance(assessment, dict):
        return "### Error\nInvalid assessment payload."
    if assessment.get("error"):
        return f"### Error\n{_as_str(assessment.get('error'))}"

    title = _as_str(assessment.get("title") or "Assessment")
    atype = _as_str(assessment.get("type") or "")
    difficulty = _as_str(assessment.get("difficulty") or "")
    questions: List[Dict[str, Any]] = assessment.get("questions") or []
    rubric = assessment.get("rubric") or []

    out: List[str] = [f"# {title}"]
    meta: List[str] = []
    if atype: meta.append(f"Type: {atype}")
    if difficulty: meta.append(f"Difficulty: {difficulty}")
    if questions: meta.append(f"Questions: {len(questions)}")
    if meta:
        out.append("\n".join(f"- {m}" for m in meta))

    if questions:
        out.append("\n## Questions")
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for idx, q in enumerate(questions, 1):
            if not isinstance(q, dict):
                out.append(f"**Q{idx}. {_as_str(q)}**")
                out.append("")
                continue
            qtext = _as_str(q.get("q") or q.get("question") or f"Question {idx}")
            out.append(f"**Q{idx}. {qtext}**")

            opts = q.get("options") or q.get("choices") or []
            if isinstance(opts, list) and opts:
                for oi, opt in enumerate(opts):
                    label = letters[oi] if oi < len(letters) else str(oi + 1)
                    out.append(f"- {label}. {_as_str(opt)}")

            ans = q.get("answer")
            if ans is not None and ans != "":
                if isinstance(ans, list):
                    out.append(f"\n> Answer: **{', '.join(_as_str(a) for a in ans)}**")
                else:
                    out.append(f"\n> Answer: **{_as_str(ans)}**")

            out.append("")  # spacing

    if rubric:
        out.append("## Rubric")
        if isinstance(rubric, list) and all(isinstance(r, dict) for r in rubric):
            out.append("| Criteria | Points |")
            out.append("|---|---:|")
            for r in rubric:
                crit = _as_str(r.get("criteria") or r.get("criterion") or r.get("desc") or "")
                pts = _as_str(r.get("points") or r.get("score") or "")
                out.append(f"| {crit} | {pts} |")
        else:
            out.append(_as_str(rubric))

    return "\n".join(out).strip() or "# Assessment\n_No content_"