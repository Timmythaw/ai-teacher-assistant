from typing import List, Dict
from flask import g, has_request_context
from utils.db import get_supabase_client


def get_dashboard_counts(supabase=None) -> Dict[str, int]:
    """Return simple counts for batches, lesson_plans and assessments.

    Uses simple selects and returns 0 on any error so caller can render safely.
    """
    if supabase is None:
        supabase = get_supabase_client()

    counts = {
        "batches": 0,
        "lesson_plans": 0,
        "assessments": 0,
    }

    try:
        res = supabase.table("batches").select("id").execute()
        counts["batches"] = len(res.data or [])
    except Exception:
        counts["batches"] = 0

    try:
        res = supabase.table("lesson_plans").select("id").execute()
        counts["lesson_plans"] = len(res.data or [])
    except Exception:
        counts["lesson_plans"] = 0

    try:
        res = supabase.table("assessments").select("id").execute()
        counts["assessments"] = len(res.data or [])
    except Exception:
        counts["assessments"] = 0

    return counts


def get_recent_activities(supabase=None, limit: int = 6) -> List[Dict]:
    """Return a merged, time-sorted list of recent activities across tables.

    Each item is a dict with keys: type (one of 'assessment','lesson_plan','batch'),
    id, title (friendly title), created_at (string).

    The function fetches recent rows from each table and merges them in Python.
    This avoids complex SQL unions and works even with RLS applied.
    """
    if supabase is None:
        supabase = get_supabase_client()

    items = []

    # Helper to safely append rows
    def _append_rows(rows, typ, title_field):
        for r in (rows or []):
            items.append({
                "type": typ,
                "id": r.get("id"),
                "title": r.get(title_field) or (r.get("name") or r.get("title") or f"{typ.title()} {r.get('id')}"),
                "created_at": r.get("created_at") or r.get("updated_at") or "",
            })

    try:
        a = supabase.table("assessments").select("id, original_filename, created_at").order("created_at", desc=True).limit(limit).execute()
        print(f"Dashboard service: assessments initial raw -> {getattr(a, 'data', None)}")
        if not getattr(a, 'data', None):
            # Try a broader select for debugging (may be restricted by RLS)
            try:
                a2 = supabase.table("assessments").select("*").order("created_at", desc=True).limit(limit).execute()
                print(f"Dashboard service: assessments fallback raw -> {getattr(a2, 'data', None)}")
                _append_rows(a2.data if getattr(a2, 'data', None) else [], "assessment", "title")
            except Exception as e:
                print(f"Dashboard service: assessments fallback error: {e}")
        else:
            _append_rows(a.data if getattr(a, "data", None) else [], "assessment", "title")
    except Exception as e:
        print(f"Dashboard service: assessments query error: {e}")

    try:
        lp = supabase.table("lesson_plans").select("id, original_filename, created_at").order("created_at", desc=True).limit(limit).execute()
        print(f"Dashboard service: lesson_plans initial raw -> {getattr(lp, 'data', None)}")
        if not getattr(lp, 'data', None):
            try:
                lp2 = supabase.table("lesson_plans").select("*").order("created_at", desc=True).limit(limit).execute()
                print(f"Dashboard service: lesson_plans fallback raw -> {getattr(lp2, 'data', None)}")
                _append_rows(lp2.data if getattr(lp2, 'data', None) else [], "lesson_plan", "title")
            except Exception as e:
                print(f"Dashboard service: lesson_plans fallback error: {e}")
        else:
            _append_rows(lp.data if getattr(lp, "data", None) else [], "lesson_plan", "title")
    except Exception as e:
        print(f"Dashboard service: lesson_plans query error: {e}")

    try:
        b = supabase.table("batches").select("id, name, created_at").order("created_at", desc=True).limit(limit).execute()
        print(f"Dashboard service: batches initial raw -> {getattr(b, 'data', None)}")
        if not getattr(b, 'data', None):
            try:
                b2 = supabase.table("batches").select("*").order("created_at", desc=True).limit(limit).execute()
                print(f"Dashboard service: batches fallback raw -> {getattr(b2, 'data', None)}")
                _append_rows(b2.data if getattr(b2, 'data', None) else [], "batch", "name")
            except Exception as e:
                print(f"Dashboard service: batches fallback error: {e}")
        else:
            _append_rows(b.data if getattr(b, "data", None) else [], "batch", "name")
    except Exception as e:
        print(f"Dashboard service: batches query error: {e}")

    # Debug: Log whether RPC user context was set in DB client (if in request context)
    try:
        if has_request_context():
            print(f"Dashboard service: g.db_user_context_set = {getattr(g, 'db_user_context_set', None)}")
    except Exception:
        pass

    # Sort merged list by created_at descending (strings assumed ISO; empty strings go last)
    try:
        items_sorted = sorted(items, key=lambda x: x.get("created_at") or "", reverse=True)
    except Exception:
        items_sorted = items

    # Limit total returned
    return items_sorted[:limit]
