"""
State store for AutoGen orchestration plans and logs.

Design goals:
- File-first persistence for reliability and local dev.
- Optional Supabase upsert/export when requested (reuses project env config).
- Minimal API: save_plan(job_id, plan), load_plan(job_id), append_logs(job_id, entries),
  export_to_supabase(job_id).

Notes:
- We do not automatically write to Supabase unless asked. The main app already
  has endpoints to persist generated artifacts (assessments, forms, etc.).
- Table name for Supabase is configurable; defaults to 'autogen_jobs'. Create
  the table with columns compatible with:
    id (text/uuid primary key), plan (jsonb), status (text), logs (jsonb), updated_at (timestamp)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import logger

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def _safe_read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed reading %s: %s", path, e)
        return None


def _safe_write_json(path: Path, data: Dict[str, Any]) -> bool:
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error("Failed writing %s: %s", path, e)
        return False


def _get_supabase_client():
    try:
        if not (SUPABASE_URL and SUPABASE_KEY):
            return None
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        logger.warning("Supabase client unavailable: %s", e)
        return None


@dataclass
class StateStore:
    root_dir: Path = Path("data/autogen_jobs")
    table_name: str = "autogen_jobs"
    prefer_db: bool = False

    def __post_init__(self):
        if isinstance(self.root_dir, str):
            self.root_dir = Path(self.root_dir)
        _ensure_dir(self.root_dir)
        self._sb = _get_supabase_client() if self.prefer_db else None

    # --- File paths ---
    def _job_path(self, job_id: str) -> Path:
        return self.root_dir / f"{job_id}.json"

    # --- Core API ---
    def save_plan(self, job_id: str, plan: Dict[str, Any]) -> bool:
        """Persist full plan to file, and optionally to Supabase if prefer_db is set."""
        plan = dict(plan or {})
        # Update book-keeping
        plan.setdefault("metadata", {}).setdefault("updated_at", _now_iso())
        ok = _safe_write_json(self._job_path(job_id), plan)
        if not ok:
            return False
        if self._sb is not None:
            try:
                status = (plan.get("state") or {}).get("status")
                logs = plan.get("logs") or []
                payload = {
                    "id": job_id,
                    "plan": plan,
                    "status": status,
                    "logs": logs,
                    "updated_at": _now_iso(),
                }
                # upsert if supported, else insert
                # Upsert and ignore response shape; rely on exceptions for errors
                _ = self._sb.table(self.table_name).upsert(payload).execute()
            except Exception as e:
                logger.warning("Supabase save_plan failed: %s", e)
        return True

    def load_plan(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load plan from file; if not found and prefer_db, try Supabase."""
        data = _safe_read_json(self._job_path(job_id))
        if data is not None:
            return data
        if self._sb is not None:
            try:
                res = self._sb.table(self.table_name).select("plan").eq("id", job_id).limit(1).execute()
                rows = getattr(res, "data", None) or []
                if rows:
                    plan = rows[0].get("plan")
                    if isinstance(plan, dict):
                        # cache to file
                        _safe_write_json(self._job_path(job_id), plan)
                        return plan
            except Exception as e:
                logger.warning("Supabase load_plan failed: %s", e)
        return None

    def append_logs(self, job_id: str, entries: List[Dict[str, Any]]) -> bool:
        """Append log entries to the stored plan."""
        data = self.load_plan(job_id) or {}
        logs = data.get("logs") or []
        logs.extend(entries or [])
        data["logs"] = logs
        data.setdefault("metadata", {}).setdefault("updated_at", _now_iso())
        return self.save_plan(job_id, data)

    # --- Optional: explicit export to Supabase on demand ---
    def export_to_supabase(self, job_id: str) -> bool:
        """Push the latest local plan to Supabase. Returns True if successful or no-op."""
        sb = _get_supabase_client()
        if sb is None:
            logger.info("Supabase export skipped: client not available")
            return False
        plan = self.load_plan(job_id)
        if not isinstance(plan, dict):
            logger.warning("export_to_supabase: no plan found for job_id=%s", job_id)
            return False
        try:
            status = (plan.get("state") or {}).get("status")
            logs = plan.get("logs") or []
            payload = {
                "id": job_id,
                "plan": plan,
                "status": status,
                "logs": logs,
                "updated_at": _now_iso(),
            }
            _ = sb.table(self.table_name).upsert(payload).execute()
            return True
        except Exception as e:
            logger.warning("Supabase export failed: %s", e)
            return False


__all__ = [
    "StateStore",
]
