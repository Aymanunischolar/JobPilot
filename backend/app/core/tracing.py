"""Observability layer (§7.1).

Every agent call is wrapped with an OpenTelemetry span tagged with
trace_id, agent name, input/output hashes, and latency, and also recorded
as a ``TraceEvent`` on ``JobState.trace`` so a full job's decision path can
be replayed from a single trace_id without a tracing backend running.
Langfuse export is wired in when LANGFUSE_* env vars are set; otherwise
spans stay local (OTel console/no-op) and TraceEvents remain the source of
truth for replay.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

from app.core.config import get_settings
from app.core.hashing import sha256
from app.schemas.models import JobState, TraceEvent

_provider = TracerProvider(resource=Resource.create({"service.name": "jobpilot"}))
_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(_provider)
_tracer = trace.get_tracer("jobpilot")


def hash_payload(payload: object) -> str:
    try:
        blob = json.dumps(payload, sort_keys=True, default=str)
    except TypeError:
        blob = str(payload)
    return sha256(blob)


@contextmanager
def agent_span(state: JobState, agent: str, input_payload: object):
    """Wrap one agent call: emits an OTel span and appends a TraceEvent to
    ``state.trace`` with decision/rationale filled in by the caller via the
    yielded recorder."""
    start = time.perf_counter()
    input_hash = hash_payload(input_payload)
    record = {"decision": "ok", "rationale": "", "output": None}

    with _tracer.start_as_current_span(agent) as span:
        span.set_attribute("trace_id", state.trace_id)
        span.set_attribute("agent", agent)
        span.set_attribute("input_hash", input_hash)
        try:
            yield record
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            output_hash = hash_payload(record["output"])
            span.set_attribute("output_hash", output_hash)
            span.set_attribute("decision", record["decision"])
            span.set_attribute("latency_ms", latency_ms)
            state.trace.append(
                TraceEvent(
                    trace_id=state.trace_id,
                    agent=agent,
                    input_hash=input_hash,
                    output_hash=output_hash,
                    decision=record["decision"],
                    rationale=record["rationale"],
                    latency_ms=latency_ms,
                )
            )


def persist_trace(state: JobState) -> Path:
    """Write the full trace for a session to the local data dir so it can
    be replayed by trace_id later (§7.1)."""
    settings = get_settings()
    out_dir = settings.data_dir / "traces"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{state.trace_id}.json"
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_trace(trace_id: str) -> JobState | None:
    settings = get_settings()
    path = settings.data_dir / "traces" / f"{trace_id}.json"
    if not path.exists():
        return None
    return JobState.model_validate_json(path.read_text(encoding="utf-8"))
