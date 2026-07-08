import { AlertCircle, GitBranch, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ApiError, getSession, submitApproval, uploadResume } from "./api/client";
import { EscalationBanner } from "./components/EscalationBanner";
import { Header } from "./components/Header";
import { PipelineLoader } from "./components/PipelineLoader";
import { PostingCard } from "./components/PostingCard";
import { PostingDetail } from "./components/PostingDetail";
import { ResumeSummary } from "./components/ResumeSummary";
import { TraceTimeline } from "./components/TraceTimeline";
import { UploadDropzone } from "./components/UploadDropzone";
import type { ApprovalDecision, JobState } from "./types";

type Screen = "landing" | "loading" | "results";

function Hero() {
  return (
    <div className="mx-auto mb-10 max-w-xl text-center">
      <div className="mx-auto mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-lg shadow-brand-500/30">
        <svg viewBox="0 0 32 32" fill="none" className="h-7 w-7">
          <path d="M16 6L18.5 13.5L26 16L18.5 18.5L16 26L13.5 18.5L6 16L13.5 13.5L16 6Z" fill="currentColor" />
        </svg>
      </div>
      <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-4xl">
        Find, score, and tailor —{" "}
        <span className="bg-gradient-to-r from-brand-600 to-violet-500 bg-clip-text text-transparent">
          you approve
        </span>
      </h1>
      <p className="mt-3 text-base text-slate-500 dark:text-slate-400">
        Upload your resume. JobPilot's agents will search real postings, score your ATS
        fit, and draft tailored resumes and cover letters — nothing gets submitted
        anywhere until you say so.
      </p>
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("landing");
  const [session, setSession] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedPostingId, setSelectedPostingId] = useState<string | null>(null);
  const [showTrace, setShowTrace] = useState(false);

  const sortedPostings = useMemo(() => {
    if (!session) return [];
    return [...session.postings].sort((a, b) => {
      const scoreA = session.ats_results[a.id]?.score ?? -1;
      const scoreB = session.ats_results[b.id]?.score ?? -1;
      return scoreB - scoreA;
    });
  }, [session]);

  const selectedPosting = sortedPostings.find((p) => p.id === selectedPostingId) ?? sortedPostings[0];

  // Sessions are shareable/bookmarkable via ?session=<id> — load one on
  // mount if present, so a link to a paused (awaiting-approval) session
  // can be sent to whoever needs to review it.
  useEffect(() => {
    const sessionId = new URLSearchParams(window.location.search).get("session");
    if (!sessionId) return;
    setScreen("loading");
    getSession(sessionId)
      .then((state) => {
        setSession(state);
        setSelectedPostingId(state.postings[0]?.id ?? null);
        setScreen("results");
      })
      .catch((e) => {
        setError(e instanceof ApiError ? e.message : "Couldn't load that session.");
        setScreen("landing");
      });
  }, []);

  async function handleFile(file: File) {
    setScreen("loading");
    setError(null);
    try {
      const state = await uploadResume(file);
      setSession(state);
      setSelectedPostingId(state.postings[0]?.id ?? null);
      setScreen("results");
      window.history.replaceState(null, "", `?session=${state.session_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong uploading your resume.");
      setScreen("landing");
    }
  }

  async function handleSampleResume() {
    setError(null);
    try {
      const res = await fetch("/sample-resume.docx");
      if (!res.ok) throw new Error("Sample resume is unavailable right now.");
      const blob = await res.blob();
      const file = new File([blob], "sample-resume.docx", { type: blob.type });
      await handleFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load the sample resume.");
    }
  }

  async function handleDecision(postingId: string, decision: ApprovalDecision) {
    if (!session) return;
    try {
      const updated = await submitApproval(session.session_id, postingId, decision, "you");
      setSession(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't record your decision — try again.");
    }
  }

  async function refreshSession() {
    if (!session) return;
    try {
      const updated = await getSession(session.session_id);
      setSession(updated);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't refresh this session.");
    }
  }

  function reset() {
    setSession(null);
    setSelectedPostingId(null);
    setError(null);
    setScreen("landing");
    window.history.replaceState(null, "", window.location.pathname);
  }

  return (
    <div className="min-h-full bg-slate-50 dark:bg-slate-950">
      <Header onReset={reset} showReset={screen === "results"} />

      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        {screen === "landing" && (
          <div className="flex min-h-[70vh] flex-col items-center justify-center">
            <Hero />
            <div className="w-full max-w-xl">
              <UploadDropzone onFile={handleFile} />
              <button
                onClick={handleSampleResume}
                className="mx-auto mt-4 block text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
              >
                Don't have a resume handy? Try a sample →
              </button>
              {error && (
                <div className="mt-4 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-500/10 dark:text-rose-400">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}
            </div>
          </div>
        )}

        {screen === "loading" && (
          <div className="flex min-h-[70vh] items-center justify-center">
            <PipelineLoader />
          </div>
        )}

        {screen === "results" && session && (
          <div className="animate-fade-in space-y-5">
            {session.escalated && <EscalationBanner reason={session.escalation_reason} />}

            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-500/10 dark:text-rose-400">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Left: resume summary + trace */}
              <div className="space-y-4 lg:col-span-3">
                {session.parsed_resume && <ResumeSummary resume={session.parsed_resume} />}

                <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                  <button
                    onClick={() => setShowTrace((v) => !v)}
                    className="flex w-full items-center justify-between text-left"
                  >
                    <span className="flex items-center gap-1.5 text-sm font-semibold text-slate-700 dark:text-slate-200">
                      <GitBranch className="h-3.5 w-3.5" /> Decision trace
                    </span>
                    <span className="text-xs text-slate-400 dark:text-slate-500">
                      {showTrace ? "Hide" : "Show"}
                    </span>
                  </button>
                  {showTrace && (
                    <div className="mt-3">
                      <TraceTimeline events={session.trace} />
                    </div>
                  )}
                </div>

                <button
                  onClick={refreshSession}
                  className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 py-2 text-xs font-medium text-slate-500 transition hover:bg-slate-100 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-800"
                >
                  <RefreshCw className="h-3 w-3" /> Refresh session
                </button>
              </div>

              {/* Middle: postings list */}
              <div className="lg:col-span-4">
                <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                  {sortedPostings.length} posting{sortedPostings.length === 1 ? "" : "s"} found
                </p>
                <div className="space-y-2.5">
                  {sortedPostings.map((posting) => (
                    <PostingCard
                      key={posting.id}
                      posting={posting}
                      ats={session.ats_results[posting.id]}
                      tailored={session.tailored[posting.id]}
                      selected={selectedPosting?.id === posting.id}
                      onSelect={() => setSelectedPostingId(posting.id)}
                    />
                  ))}
                  {sortedPostings.length === 0 && (
                    <p className="rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400 dark:border-slate-800 dark:text-slate-500">
                      No postings found for this resume.
                    </p>
                  )}
                </div>
              </div>

              {/* Right: posting detail */}
              <div className="lg:col-span-5">
                {selectedPosting ? (
                  <PostingDetail
                    posting={selectedPosting}
                    ats={session.ats_results[selectedPosting.id]}
                    tailored={session.tailored[selectedPosting.id]}
                    approval={session.approvals[selectedPosting.id]}
                    applicationResult={session.application_results[selectedPosting.id]}
                    resume={session.parsed_resume}
                    onApprove={handleDecision}
                    onReject={handleDecision}
                  />
                ) : (
                  <div className="flex h-full min-h-[200px] items-center justify-center rounded-2xl border border-dashed border-slate-200 text-sm text-slate-400 dark:border-slate-800 dark:text-slate-500">
                    Select a posting to see its ATS breakdown and tailored resume.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
