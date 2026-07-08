"""Local session/state persistence.

Resume and personal data are stored locally, never sent to third parties
beyond the LLM/search providers required for the current step (§6.4). This
is a filesystem-backed store suitable for the reproducible-demo scope of
this project; swapping in a real encrypted database is a drop-in
replacement behind the same three functions.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.schemas.models import JobState


def save_state(state: JobState) -> None:
    settings = get_settings()
    out_dir = settings.data_dir / "sessions"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{state.session_id}.json"
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def load_state(session_id: str) -> JobState | None:
    settings = get_settings()
    path = settings.data_dir / "sessions" / f"{session_id}.json"
    if not path.exists():
        return None
    return JobState.model_validate_json(path.read_text(encoding="utf-8"))


def delete_state(session_id: str) -> None:
    settings = get_settings()
    path = settings.data_dir / "sessions" / f"{session_id}.json"
    if path.exists():
        path.unlink()
