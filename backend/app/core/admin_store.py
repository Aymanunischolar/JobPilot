"""Durable, queryable run log — every resume upload, agent response, and
approval decision, independent of the LangGraph checkpoint.

The checkpoint store (manager.py) is optimized for resuming a paused
graph; it isn't meant to be listed or browsed. This module persists a
denormalized snapshot of each ``JobState`` (resume, postings, ATS
results, tailored output, trace/agent decisions, approvals) to a plain
JSONB table every time it changes, so the admin dashboard has something
simple and fast to query — a run's history survives even if the
checkpoint store is ever cleared.

No-ops silently when DATABASE_URL isn't set (falls back to whatever the
in-memory checkpoint already provides for the current process).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.schemas.models import JobState

_pool: ConnectionPool | None = None
_schema_ready = False

# 5 attempts — Neon can suspend its compute after idling, and a fresh
# connection after that requires a cold start that can take longer than
# a couple of short retries.
_retry_transient = retry(
    retry=retry_if_exception_type(psycopg.OperationalError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    reraise=True,
)


def _get_pool() -> ConnectionPool | None:
    global _pool, _schema_ready
    settings = get_settings()
    if not settings.checkpoint_dsn:
        return None
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.checkpoint_dsn,
            max_size=5,
            # Recycle connections proactively rather than waiting to
            # discover Neon already closed them mid-query; check_connection
            # pings before handing one out at all.
            max_idle=60,
            max_lifetime=600,
            check=ConnectionPool.check_connection,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        _pool.wait(timeout=10)
    if not _schema_ready:
        with _pool.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    session_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    candidate_name TEXT,
                    current_step TEXT NOT NULL,
                    escalated BOOLEAN NOT NULL DEFAULT FALSE,
                    posting_count INTEGER NOT NULL DEFAULT 0,
                    job_state JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        _schema_ready = True
    return _pool


def close_pool() -> None:
    global _pool, _schema_ready
    if _pool is not None:
        _pool.close()
        _pool = None
        _schema_ready = False


@_retry_transient
def save_run(job_state: JobState) -> None:
    """Upserts the full JobState for this session. Called after every
    pipeline step that changes state (initial run, approval, resume)."""
    pool = _get_pool()
    if pool is None:
        return

    candidate_name = job_state.parsed_resume.full_name if job_state.parsed_resume else None
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO pipeline_runs
                (session_id, trace_id, candidate_name, current_step, escalated, posting_count, job_state, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                trace_id = EXCLUDED.trace_id,
                candidate_name = EXCLUDED.candidate_name,
                current_step = EXCLUDED.current_step,
                escalated = EXCLUDED.escalated,
                posting_count = EXCLUDED.posting_count,
                job_state = EXCLUDED.job_state,
                updated_at = EXCLUDED.updated_at
            """,
            (
                job_state.session_id,
                job_state.trace_id,
                candidate_name,
                job_state.current_step,
                job_state.escalated,
                len(job_state.postings),
                job_state.model_dump_json(),
                datetime.now(timezone.utc),
            ),
        )


@_retry_transient
def list_runs(limit: int = 100) -> list[dict]:
    pool = _get_pool()
    if pool is None:
        return []
    with pool.connection() as conn:
        cur = conn.execute(
            """
            SELECT session_id, trace_id, candidate_name, current_step, escalated,
                   posting_count, created_at, updated_at
            FROM pipeline_runs
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


@_retry_transient
def get_run(session_id: str) -> JobState | None:
    pool = _get_pool()
    if pool is None:
        return None
    with pool.connection() as conn:
        cur = conn.execute(
            "SELECT job_state FROM pipeline_runs WHERE session_id = %s",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        raw = row["job_state"]
        return JobState.model_validate(raw if isinstance(raw, dict) else json.loads(raw))
