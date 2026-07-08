# JobPilot

An autonomous multi-agent system for job discovery, ATS scoring, and resume
tailoring — with a human approval gate before any application ever leaves
the system.

Full design rationale lives in
[`docs/JobPilot_Architecture_Document.docx`](docs/JobPilot_Architecture_Document.docx).
This README covers what's implemented and how to run it.

## Why this exists

Job seekers manually repeat four slow steps for every posting: find the
job, guess whether their resume is a good match, rewrite the resume by
hand, and fill out the application. JobPilot automates the first three and
prepares (never blindly submits) the fourth, while keeping a human as the
final authority on every submission.

The one non-negotiable principle behind every design decision here: agents
may accelerate judgment, but they must never fabricate qualifications or
act irreversibly without approval.

## Architecture

A supervisor (Manager) pattern, not a linear pipeline or an agent-to-agent
mesh — every hand-off is a single, loggable edge into and out of the
Manager, which keeps the control flow auditable and lets any one agent be
swapped without touching the others.

```
USER (resume + preferences)
        |
        v
  MANAGER AGENT (LangGraph supervisor — routes, gates, logs)
   |         |          |
   v         v          v
Resume    Job Search   ATS Scorer
Parser    (Tavily)     (score + keyword gap, gate >= 70%)
   |         |          |
   +---------+----------+
             v
        Tailor Agent  --->  Manager QA Check (hallucination scan)
                                   |
                                   v
                          Human Approval Gate (required)
                                   |
                                   v
                          Application Agent (Playwright;
                          auto-submit only on allow-listed forms)
```

| Agent | Responsibility |
|---|---|
| **Manager** | Routes `search → score → tailor → QA → human gate → apply`; owns both quality gates; logs every hop |
| **Resume Parser** | Unstructured PDF/DOCX → typed `ParsedResume` (LLM extraction + regex fallback for dates/contact) |
| **Job Search** | Tavily-driven search, hybrid keyword + embedding ranking, canonical-URL/JD-hash dedup |
| **ATS Scorer** | Weighted match score (keywords 40% · title/seniority 20% · experience 15% · education 10% · formatting 15%) + `missing_keywords` + `fit_rationale` |
| **Tailor** | Reorders/rewords real bullets only — every bullet cites a `source_bullet_id`; drafts a cover letter and a diff view |
| **Application** | Playwright form-fill, strictly gated behind human approval; auto-submit only on an explicit allow-list |

### Guardrails (§6 of the architecture doc)

- **Human-in-the-loop boundary** — the Application Agent node in the
  LangGraph graph has exactly one incoming edge, from the Human Approval
  Gate, and the graph is compiled with `interrupt_before=["application_agent"]`.
  There is no code path that reaches it without a recorded approval.
- **Hallucination / faithfulness checker** — a structural check (every
  `source_bullet_id` must exist in the original resume) followed by an
  LLM-as-judge semantic check (flags any metric/skill/claim not present in
  the cited source bullet). Failures route back to the Tailor Agent with
  the specific violating bullet, not a generic retry.
- **Third-party ToS compliance** — auto-submit is restricted to an
  explicit host allow-list (`AUTO_SUBMIT_ALLOWLIST`); every other channel
  stops at a human click.
- **Data handling** — resumes and personal data stay in a local store
  (`.jobpilot_data/`, gitignored); nothing is sent to third parties beyond
  the LLM/search providers required for the current step.

### Durable checkpointing (optional)

The Human Approval Gate can leave a session paused for an arbitrary
amount of time — a human has to actually look at it. By default that
paused state lives in memory and doesn't survive a process restart. Set
`DATABASE_URL` (any Postgres, e.g. Neon) to switch to a durable,
Postgres-backed checkpointer instead — LangGraph's tables are created in
their own schema (`DATABASE_SCHEMA`, default `jobpilot`), never in
`public`, so this is safe to point at a database another app already
uses. Uses the sync `PostgresSaver` wrapped in a thread-executor adapter
rather than the async driver, deliberately — psycopg's async mode needs
Python's SelectorEventLoop, which conflicts with Playwright's
ProactorEventLoop requirement for subprocess support on Windows.

## Project layout

```
backend/app/
  schemas/models.py      Typed contracts (JobState + all sub-models, §5)
  agents/                One module per agent, one graph node each
  core/                  Config, pluggable LLM client, tracing, hashing, local store
  api/                   FastAPI routes
  eval/                  Evaluation harness + hand-labeled fixtures (§7)
backend/tests/            pytest unit tests
frontend/src/
  api/client.ts           Typed fetch wrapper for the backend
  types.ts                Mirrors backend/app/schemas/models.py
  components/             Upload, ATS score ring, tailored-resume diff, approval controls, ...
  App.tsx                 Screen state machine: landing -> loading -> results
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium

cp .env.example .env         # fill in OPENAI_API_KEY / TAVILY_API_KEY, etc.
```

## Running

```bash
cd backend
uvicorn app.api.main:app --reload
```

- `POST /api/resume/upload` — upload a PDF/DOCX resume; runs the pipeline
  through the Human Approval Gate and returns the paused `JobState`
  (postings, ATS scores, tailored drafts, diff views).
- `GET /api/sessions/{session_id}` — inspect the current paused state.
- `POST /api/sessions/{session_id}/approvals` — record an approve/reject
  decision for one posting; approving resumes the graph into the
  Application Agent for that posting.
- `GET /api/trace/{trace_id}` — replay the full decision trail for a run.

Or with Docker:

```bash
docker compose up --build
```

## Frontend

A React + TypeScript + Tailwind UI lives in [`frontend/`](frontend/) —
resume upload, live pipeline progress, ATS score breakdowns, a tailored-
resume diff view, and the approve/reject controls for the human approval
gate. See [`frontend/README.md`](frontend/README.md) for details.

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /api to the backend on :8000
```

Start the backend first (above), then the frontend. No resume handy? The
landing page has a "Try a sample" link.

## Tests & evaluation

```bash
cd backend
python -m pytest -q
python -m app.eval.harness   # §7 metrics against the fixtures in app/eval/data/
```

The eval harness tracks the five metrics defined in the architecture doc:
job relevance precision (≥85%), ATS score calibration (±7 points),
tailoring faithfulness (100%), keyword-gap closure (≥80%), and manager
gate accuracy (≥90%) — against small, hand-labeled fixture sets checked
into `backend/app/eval/data/`. Swap in your own labeled examples as the
system is used against real postings.

## Technology stack

| Layer | Choice |
|---|---|
| Orchestration | LangGraph |
| Search | Tavily API |
| LLMs | OpenAI + Gemini, pluggable via `LLM_PROVIDER` |
| Schema validation | Pydantic |
| API | FastAPI |
| Frontend | React + TypeScript + Vite + Tailwind CSS |
| Browser automation | Playwright |
| Tracing | OpenTelemetry spans + local trace replay by `trace_id` |
| Checkpointing | In-memory by default; optional Postgres (any provider, e.g. Neon) via `DATABASE_URL` |
| Deployment | Docker + GitHub Actions CI |

## Delivery roadmap

1. **Core pipeline** — Resume Parser + Job Search + ATS Scorer, eval harness running ✅
2. **Tailoring + guardrails** — Tailor Agent + faithfulness checker + Manager QA gate ✅
3. **Human-gated automation** — Approval Gate + Application Agent (allow-listed auto-submit) ✅
4. **Observability & polish** — tracing dashboard, demo video, hosted eval report

## Author

Ayman Rehman — AI Engineer, Agentic AI & LLM Agents
germanayman@gmail.com · [linkedin.com/in/ayman-rehman](https://linkedin.com/in/ayman-rehman)
