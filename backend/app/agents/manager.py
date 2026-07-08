"""Manager Agent — the LangGraph supervisor (§3, §4.1).

The Manager is the only stateful orchestrator. It does not call external
tools directly; its job is routing, gating, and logging (§4.1). No
specialist agent talks directly to another — every hand-off is a single,
loggable edge into and out of the Manager (§3.2), which is why every node
in this graph is a thin wrapper that calls exactly one specialist agent
function and records a TraceEvent.

Routing (§4.1 table): search → score → tailor → QA → human gate → apply
  Gate 1 — ATS threshold: rejects / routes back to Job Search if predicted
           ATS score < 70% for every posting.
  Gate 2 — Faithfulness check: runs the hallucination checker against
           every Tailor Agent output before it can proceed.
  Escalation: flags ambiguous cases (borderline ATS score, low-confidence
           parse) for human review instead of guessing.

The Application Agent node is only reachable via an interrupt-gated edge
from the Human Approval Gate node — there is no path in this graph that
reaches ``application_agent`` without the graph having paused for human
input first (§6.1).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional, TypedDict

import psycopg
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# 3 attempts, not 2 — Neon can drop several pooled connections in one
# burst (e.g. compute suspend/resume), so a single retry sometimes just
# lands on another connection that's about to die too.
_retry_transient_pg = retry(
    retry=retry_if_exception_type(psycopg.OperationalError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=3),
    reraise=True,
)

from app.agents.application import submit_application
from app.agents.ats_scorer import score_resume
from app.agents.faithfulness import check_faithfulness
from app.agents.job_search import search_jobs
from app.core.config import get_settings
from app.agents.resume_parser import parse_resume
from app.agents.tailor import tailor_resume
from app.core import admin_store
from app.core.tracing import agent_span, persist_trace
from app.schemas.models import (
    ApprovalDecision,
    ApprovalStatus,
    Channel,
    FaithfulnessStatus,
    JobState,
)

MAX_SEARCH_RETRIES = 1
MAX_TAILOR_RETRIES = 2
ATS_BORDERLINE_BAND = 5.0  # points either side of the threshold


class GraphState(TypedDict):
    job_state: JobState
    resume_bytes: Optional[bytes]
    resume_filename: Optional[str]
    search_retries: int
    tailor_retries: dict[str, int]
    resume_file_path: Optional[str]  # local path used by the Application Agent


def _is_sparse_parse(job_state: JobState) -> bool:
    resume = job_state.parsed_resume
    return resume is None or (not resume.roles and not resume.skills)


def _is_borderline(score: float, threshold: float, band: float = ATS_BORDERLINE_BAND) -> bool:
    return abs(score - threshold) <= band


# --------------------------------------------------------------------------
# Nodes
# --------------------------------------------------------------------------


def resume_parser_node(state: GraphState) -> dict:
    job_state = state["job_state"]
    if job_state.parsed_resume is not None:
        return {}

    with agent_span(job_state, "resume_parser", {"filename": state.get("resume_filename")}) as rec:
        parsed = parse_resume(state["resume_bytes"], state["resume_filename"])
        job_state.parsed_resume = parsed
        rec["output"] = parsed.model_dump()
        if _is_sparse_parse(job_state):
            job_state.escalated = True
            job_state.escalation_reason = (
                "low-confidence resume parse: few or no roles/skills extracted"
            )
            rec["decision"] = "escalate"
            rec["rationale"] = job_state.escalation_reason
        else:
            rec["decision"] = "pass"
            rec["rationale"] = f"extracted {len(parsed.roles)} roles, {len(parsed.skills)} skills"

    job_state.current_step = "resume_parsed"
    return {"job_state": job_state}


def job_search_node(state: GraphState) -> dict:
    job_state = state["job_state"]
    with agent_span(job_state, "job_search", {"skills": job_state.parsed_resume.skills}) as rec:
        postings = search_jobs(job_state.parsed_resume)
        job_state.postings = postings
        rec["output"] = [p.model_dump() for p in postings]
        rec["decision"] = "pass" if postings else "no_results"
        rec["rationale"] = f"found {len(postings)} deduped, ranked postings"

    job_state.current_step = "postings_found"
    return {
        "job_state": job_state,
        "search_retries": state.get("search_retries", 0) + 1,
    }


def ats_scorer_node(state: GraphState) -> dict:
    job_state = state["job_state"]
    for posting in job_state.postings:
        if posting.id in job_state.ats_results:
            continue
        with agent_span(job_state, "ats_scorer", {"posting_id": posting.id}) as rec:
            result = score_resume(job_state.parsed_resume, posting)
            job_state.ats_results[posting.id] = result
            rec["output"] = result.model_dump()
            rec["decision"] = "pass" if result.passed_gate else "reject"
            rec["rationale"] = result.fit_rationale

            if _is_borderline(result.score, 70.0):
                job_state.escalated = True
                job_state.escalation_reason = (
                    f"borderline ATS score ({result.score:.1f}) for posting {posting.id}"
                )

    job_state.current_step = "ats_scored"
    return {"job_state": job_state}


def tailor_node(state: GraphState) -> dict:
    job_state = state["job_state"]
    tailor_retries = dict(state.get("tailor_retries", {}))

    qualifying = [
        p for p in job_state.postings
        if job_state.ats_results.get(p.id) and job_state.ats_results[p.id].passed_gate
    ]

    for posting in qualifying:
        existing = job_state.tailored.get(posting.id)
        needs_tailoring = existing is None or existing.faithfulness_status in (
            FaithfulnessStatus.FAILED_STRUCTURAL,
            FaithfulnessStatus.FAILED_SEMANTIC,
        )
        if not needs_tailoring:
            continue
        if existing is not None:
            tailor_retries[posting.id] = tailor_retries.get(posting.id, 0) + 1

        with agent_span(job_state, "tailor", {"posting_id": posting.id}) as rec:
            tailored = tailor_resume(
                job_state.parsed_resume, posting, job_state.ats_results[posting.id]
            )
            job_state.tailored[posting.id] = tailored
            rec["output"] = tailored.model_dump()
            rec["decision"] = "drafted"
            rec["rationale"] = (
                f"retry {tailor_retries.get(posting.id, 0)}"
                if existing is not None
                else "initial draft"
            )

    job_state.current_step = "tailored"
    return {"job_state": job_state, "tailor_retries": tailor_retries}


def qa_check_node(state: GraphState) -> dict:
    """Manager QA Check — the hallucination/faithfulness gate (§6.2,
    Gate 2 in the routing table)."""
    job_state = state["job_state"]
    for posting_id, tailored in job_state.tailored.items():
        if tailored.faithfulness_status == FaithfulnessStatus.PASSED:
            continue
        with agent_span(job_state, "manager_qa_check", {"posting_id": posting_id}) as rec:
            checked = check_faithfulness(job_state.parsed_resume, tailored)
            job_state.tailored[posting_id] = checked
            rec["output"] = checked.model_dump()
            rec["decision"] = checked.faithfulness_status.value
            rec["rationale"] = "; ".join(checked.faithfulness_violations) or "faithful"

    job_state.current_step = "qa_checked"
    return {"job_state": job_state}


def human_approval_gate_node(state: GraphState) -> dict:
    """No incoming edge bypasses this node on the way to the Application
    Agent (§6.1). The graph is compiled with ``interrupt_before=
    ["application_agent"]`` — execution always pauses immediately after
    this node runs, and only resumes once an external caller has recorded
    an approval decision in ``job_state.approvals``."""
    job_state = state["job_state"]
    job_state.current_step = "awaiting_human_approval"
    return {"job_state": job_state}


async def application_agent_node(state: GraphState) -> dict:
    job_state = state["job_state"]
    resume_file_path = state.get("resume_file_path") or ""

    for posting_id, approval in job_state.approvals.items():
        if approval.decision != ApprovalDecision.APPROVED:
            continue
        if posting_id in job_state.application_results:
            continue  # already processed on a prior resume of this thread
        posting = next((p for p in job_state.postings if p.id == posting_id), None)
        tailored = job_state.tailored.get(posting_id)
        if posting is None or tailored is None:
            continue

        with agent_span(job_state, "application_agent", {"posting_id": posting_id}) as rec:
            result = await submit_application(posting, tailored, approval, resume_file_path)
            job_state.application_results[posting_id] = result
            rec["output"] = result
            rec["decision"] = result["action"]
            rec["rationale"] = f"channel={result['channel']} auto_submitted={result['auto_submitted']}"

    job_state.current_step = "applications_processed"
    return {"job_state": job_state}


# --------------------------------------------------------------------------
# Conditional routing
# --------------------------------------------------------------------------


def route_after_ats(state: GraphState) -> str:
    job_state = state["job_state"]
    passing = [
        p for p in job_state.postings
        if job_state.ats_results.get(p.id) and job_state.ats_results[p.id].passed_gate
    ]
    if passing:
        return "tailor"
    if state.get("search_retries", 0) < MAX_SEARCH_RETRIES:
        return "retry_search"
    job_state.escalated = True
    job_state.escalation_reason = "no postings passed the ATS gate after retrying search"
    return "no_matches"


def route_after_qa(state: GraphState) -> str:
    job_state = state["job_state"]
    tailor_retries = state.get("tailor_retries", {})
    for posting_id, tailored in job_state.tailored.items():
        if tailored.faithfulness_status == FaithfulnessStatus.PASSED:
            continue
        if tailor_retries.get(posting_id, 0) < MAX_TAILOR_RETRIES:
            return "retry_tailor"
    # anything still failing here has exhausted retries — flag and move on
    # with only the passed ones (there may be zero, which the approval
    # gate / API layer surfaces to the human as "nothing ready").
    for posting_id, tailored in job_state.tailored.items():
        if tailored.faithfulness_status != FaithfulnessStatus.PASSED:
            job_state.escalated = True
            job_state.escalation_reason = (
                f"posting {posting_id} exhausted tailoring retries without passing "
                f"the faithfulness gate"
            )
    return "human_approval"


# --------------------------------------------------------------------------
# Graph assembly
# --------------------------------------------------------------------------


class _ThreadedCheckpointSaver(BaseCheckpointSaver):
    """Adapts a sync checkpoint saver (e.g. ``PostgresSaver``) so it can
    be driven by LangGraph's async graph execution (``ainvoke`` /
    ``aget_state`` / ``aupdate_state``), by running each sync call in a
    worker thread via ``asyncio.to_thread``.

    This exists instead of using ``AsyncPostgresSaver`` directly because
    psycopg's async mode requires Python's SelectorEventLoop, while
    Playwright's async API (used by the Application Agent, §4.6) requires
    ProactorEventLoop for subprocess support on Windows — the two cannot
    coexist in the same event loop. Running the *sync* psycopg driver in
    a thread pool sidesteps that conflict entirely, since sync psycopg
    doesn't care which event loop policy is active.
    """

    def __init__(self, sync_saver):
        super().__init__(serde=sync_saver.serde)
        self._saver = sync_saver

    # Neon (and other serverless/managed Postgres) proactively terminates
    # idle connections, sometimes several in one burst (e.g. compute
    # suspend/resume). psycopg_pool detects and evicts a dead connection
    # the moment it's touched, but the in-flight query riding on it at
    # that moment still fails outright — retrying gives the pool a chance
    # to hand back a connection it has already refreshed.
    @_retry_transient_pg
    def get_tuple(self, config):
        return self._saver.get_tuple(config)

    def list(self, config, *, filter=None, before=None, limit=None):
        return self._saver.list(config, filter=filter, before=before, limit=limit)

    @_retry_transient_pg
    def put(self, config, checkpoint, metadata, new_versions):
        return self._saver.put(config, checkpoint, metadata, new_versions)

    @_retry_transient_pg
    def put_writes(self, config, writes, task_id, task_path=""):
        return self._saver.put_writes(config, writes, task_id, task_path)

    def get_next_version(self, current, channel):
        return self._saver.get_next_version(current, channel)

    async def aget_tuple(self, config):
        return await asyncio.to_thread(self._saver.get_tuple, config)

    async def alist(self, config, *, filter=None, before=None, limit=None) -> AsyncIterator[Any]:
        def _collect():
            return list(self._saver.list(config, filter=filter, before=before, limit=limit))

        for item in await asyncio.to_thread(_collect):
            yield item

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self._saver.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        await asyncio.to_thread(self._saver.put_writes, config, writes, task_id, task_path)


_checkpoint_pool = None  # psycopg_pool.ConnectionPool, when Postgres-backed


def _build_checkpointer() -> BaseCheckpointSaver:
    """Postgres-backed when DATABASE_URL is set, so the Human Approval
    Gate's paused state survives a process restart; otherwise an
    in-memory checkpointer (fine for local/demo use — state just doesn't
    outlive the process).

    Uses the *sync* PostgresSaver, not the async variant, deliberately:
    psycopg's async mode requires Python's SelectorEventLoop, but
    Playwright's async API (Application Agent, §4.6) requires
    ProactorEventLoop for subprocess support on Windows — the two can't
    coexist in one event loop. LangGraph runs sync checkpointers through
    a thread executor automatically when the graph is invoked via
    ``ainvoke``/``aget_state``/``aupdate_state``, so this is transparent
    to the rest of the graph.
    """
    global _checkpoint_pool
    settings = get_settings()
    if not settings.checkpoint_dsn:
        return MemorySaver()

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    _checkpoint_pool = ConnectionPool(
        conninfo=settings.checkpoint_dsn,
        max_size=10,
        # Neon (and other serverless Postgres) closes connections that sit
        # idle for a while, sometimes in bursts (e.g. compute suspend).
        # Recycling proactively — before the server does it to us — means
        # requests hit a connection we know is fresh instead of finding
        # out it's dead mid-query.
        max_idle=120,
        max_lifetime=1200,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    _checkpoint_pool.wait(timeout=10)
    saver = PostgresSaver(_checkpoint_pool)
    saver.setup()  # idempotent — safe to call on every process start
    return _ThreadedCheckpointSaver(saver)


def close_checkpoint_pool() -> None:
    """Call on application shutdown to release pooled Postgres
    connections cleanly."""
    global _checkpoint_pool
    if _checkpoint_pool is not None:
        _checkpoint_pool.close()
        _checkpoint_pool = None


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("resume_parser", resume_parser_node)
    graph.add_node("job_search", job_search_node)
    graph.add_node("ats_scorer", ats_scorer_node)
    graph.add_node("tailor", tailor_node)
    graph.add_node("qa_check", qa_check_node)
    graph.add_node("human_approval", human_approval_gate_node)
    graph.add_node("application_agent", application_agent_node)

    graph.add_edge(START, "resume_parser")
    graph.add_edge("resume_parser", "job_search")
    graph.add_edge("job_search", "ats_scorer")

    graph.add_conditional_edges(
        "ats_scorer",
        route_after_ats,
        {
            "tailor": "tailor",
            "retry_search": "job_search",
            "no_matches": END,
        },
    )

    graph.add_edge("tailor", "qa_check")

    graph.add_conditional_edges(
        "qa_check",
        route_after_qa,
        {
            "retry_tailor": "tailor",
            "human_approval": "human_approval",
        },
    )

    graph.add_edge("human_approval", "application_agent")
    graph.add_edge("application_agent", END)

    checkpointer = _build_checkpointer()
    # The Application Agent has exactly one incoming edge, from the Human
    # Approval Gate, and the graph always interrupts immediately before it
    # — so nothing reaches it without a resume triggered by a recorded
    # approval (§6.1).
    return graph.compile(checkpointer=checkpointer, interrupt_before=["application_agent"])


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


async def run_pipeline(
    resume_bytes: bytes, resume_filename: str, thread_id: str, resume_file_path: str = ""
) -> JobState:
    """Runs the graph from the start through the Human Approval Gate,
    where it will pause (interrupt_before=['application_agent'])."""
    graph = get_graph()
    initial: GraphState = {
        "job_state": JobState(session_id=thread_id, trace_id=thread_id),
        "resume_bytes": resume_bytes,
        "resume_filename": resume_filename,
        "search_retries": 0,
        "tailor_retries": {},
        "resume_file_path": resume_file_path,
    }
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(initial, config=config)
    job_state = result["job_state"]
    persist_trace(job_state)
    await asyncio.to_thread(admin_store.save_run, job_state)
    return job_state


async def resume_after_approval(thread_id: str) -> JobState:
    """Call after recording an approval decision in JobState.approvals to
    let the graph proceed past the Human Approval Gate into the
    Application Agent."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(None, config=config)
    job_state = result["job_state"]
    persist_trace(job_state)
    await asyncio.to_thread(admin_store.save_run, job_state)
    return job_state


async def get_state_snapshot(thread_id: str) -> JobState | None:
    """Read the current JobState for a session without resuming the
    graph — used by the API to show postings/ATS results/tailored drafts
    while the graph is paused at the Human Approval Gate.

    Uses the graph's async state accessor (``aget_state``) rather than
    the sync ``get_state`` — when Postgres-backed, the checkpoint read is
    a blocking network call, and this may be invoked from an async
    FastAPI route handler where blocking the event loop is not
    acceptable (§7: end-to-end latency target < 60s)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    if not snapshot or not snapshot.values:
        return None
    return snapshot.values["job_state"]


async def record_approval(
    thread_id: str,
    posting_id: str,
    decision: ApprovalDecision,
    approved_by: str | None,
    channel: Channel | None,
) -> JobState:
    """Records a human approval/rejection decision into the paused
    graph's checkpointed state. This is the only place JobState.approvals
    is written — the Application Agent node only ever sees decisions that
    passed through here (§6.1)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = await graph.aget_state(config)
    if not snapshot or not snapshot.values:
        raise ValueError(f"No paused session found for thread_id={thread_id!r}")

    job_state: JobState = snapshot.values["job_state"]
    job_state.approvals[posting_id] = ApprovalStatus(
        decision=decision,
        channel=channel,
        approved_by=approved_by,
        decided_at=datetime.now(timezone.utc),
    )
    await graph.aupdate_state(config, {"job_state": job_state})
    await asyncio.to_thread(admin_store.save_run, job_state)
    return job_state
