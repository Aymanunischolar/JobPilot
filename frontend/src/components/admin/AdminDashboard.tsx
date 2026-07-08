import { AlertCircle, LogOut, RefreshCw, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ApiError, getAdminRun, listAdminRuns, submitApproval } from "../../api/client";
import type { ApprovalDecision, JobState, RunSummary } from "../../types";
import { EscalationBanner } from "../EscalationBanner";
import { PostingCard } from "../PostingCard";
import { PostingDetail } from "../PostingDetail";
import { ResumeSummary } from "../ResumeSummary";
import { StatusPill } from "../StatusPill";
import { TraceTimeline } from "../TraceTimeline";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AdminDashboard({
  credentials,
  onLogout,
}: {
  credentials: { username: string; password: string };
  onLogout: () => void;
}) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<JobState | null>(null);
  const [selectedPostingId, setSelectedPostingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);

  async function loadRuns() {
    setLoadingList(true);
    setError(null);
    try {
      const data = await listAdminRuns(credentials.username, credentials.password);
      setRuns(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load runs.");
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function selectRun(sessionId: string) {
    setSelectedId(sessionId);
    setDetail(null);
    setSelectedPostingId(null);
    setLoadingDetail(true);
    setError(null);
    try {
      const state = await getAdminRun(credentials.username, credentials.password, sessionId);
      setDetail(state);
      setSelectedPostingId(state.postings[0]?.id ?? null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't load this run.");
    } finally {
      setLoadingDetail(false);
    }
  }

  async function handleDecision(postingId: string, decision: ApprovalDecision) {
    if (!detail) return;
    try {
      const updated = await submitApproval(detail.session_id, postingId, decision, credentials.username);
      setDetail(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't record decision.");
    }
  }

  const sortedPostings = useMemo(() => {
    if (!detail) return [];
    return [...detail.postings].sort((a, b) => {
      const scoreA = detail.ats_results[a.id]?.score ?? -1;
      const scoreB = detail.ats_results[b.id]?.score ?? -1;
      return scoreB - scoreA;
    });
  }, [detail]);

  const selectedPosting = sortedPostings.find((p) => p.id === selectedPostingId) ?? sortedPostings[0];

  return (
    <div className="min-h-full bg-slate-50 dark:bg-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/80 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/80">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm shadow-brand-500/30">
              <Users className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-bold tracking-tight text-slate-900 dark:text-white">
                JobPilot Admin
              </p>
              <p className="hidden text-[11px] leading-none text-slate-400 dark:text-slate-500 sm:block">
                {runs.length} run{runs.length === 1 ? "" : "s"} recorded
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadRuns}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Refresh</span>
            </button>
            <button
              onClick={onLogout}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        {error && (
          <div className="mb-4 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-500/10 dark:text-rose-400">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
          <div className="lg:col-span-4">
            <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              Runs
            </p>
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
              {loadingList ? (
                <p className="p-4 text-sm text-slate-400 dark:text-slate-500">Loading…</p>
              ) : runs.length === 0 ? (
                <p className="p-4 text-sm text-slate-400 dark:text-slate-500">
                  No runs recorded yet — they show up here as candidates upload resumes.
                </p>
              ) : (
                <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                  {runs.map((run) => (
                    <li key={run.session_id}>
                      <button
                        onClick={() => selectRun(run.session_id)}
                        className={`block w-full px-4 py-3 text-left transition ${
                          selectedId === run.session_id
                            ? "bg-brand-50 dark:bg-brand-500/10"
                            : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-semibold text-slate-900 dark:text-white">
                            {run.candidate_name ?? "Unknown candidate"}
                          </span>
                          {run.escalated && <StatusPill tone="warning">Flagged</StatusPill>}
                        </div>
                        <div className="mt-1 flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
                          <span>{run.posting_count} postings</span>
                          <span>·</span>
                          <span className="capitalize">{run.current_step.replace(/_/g, " ")}</span>
                        </div>
                        <div className="mt-1 text-[11px] text-slate-400 dark:text-slate-600">
                          {formatDate(run.updated_at)} · {run.session_id}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="lg:col-span-8">
            {!selectedId && (
              <div className="flex h-full min-h-[300px] items-center justify-center rounded-2xl border border-dashed border-slate-200 text-sm text-slate-400 dark:border-slate-800 dark:text-slate-500">
                Select a run to see the parsed resume, ATS responses, tailored output, and agent trace.
              </div>
            )}

            {selectedId && loadingDetail && (
              <div className="flex h-full min-h-[300px] items-center justify-center text-sm text-slate-400 dark:text-slate-500">
                Loading run…
              </div>
            )}

            {detail && !loadingDetail && (
              <div className="space-y-4">
                {detail.escalated && <EscalationBanner reason={detail.escalation_reason} />}

                {detail.parsed_resume && <ResumeSummary resume={detail.parsed_resume} />}

                <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                  <p className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-200">
                    Agent decision trace
                  </p>
                  <TraceTimeline events={detail.trace} />
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="space-y-2.5">
                    {sortedPostings.map((posting) => (
                      <PostingCard
                        key={posting.id}
                        posting={posting}
                        ats={detail.ats_results[posting.id]}
                        tailored={detail.tailored[posting.id]}
                        selected={selectedPosting?.id === posting.id}
                        onSelect={() => setSelectedPostingId(posting.id)}
                      />
                    ))}
                  </div>
                  <div>
                    {selectedPosting && (
                      <PostingDetail
                        posting={selectedPosting}
                        ats={detail.ats_results[selectedPosting.id]}
                        tailored={detail.tailored[selectedPosting.id]}
                        approval={detail.approvals[selectedPosting.id]}
                        applicationResult={detail.application_results[selectedPosting.id]}
                        resume={detail.parsed_resume}
                        onApprove={handleDecision}
                        onReject={handleDecision}
                      />
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
