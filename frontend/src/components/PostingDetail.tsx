import { AlertTriangle, Mail, Sparkles } from "lucide-react";
import { useState } from "react";
import type {
  ApplicationResult,
  ApprovalDecision,
  ApprovalStatus,
  ATSResult,
  JobPosting,
  ParsedResume,
  TailoredResume,
} from "../types";
import { ApprovalControls } from "./ApprovalControls";
import { DiffBullets } from "./DiffBullets";
import { ScoreRing } from "./ScoreRing";
import { SignalBars } from "./SignalBars";
import { StatusPill } from "./StatusPill";

type Tab = "fit" | "resume" | "cover-letter";

export function PostingDetail({
  posting,
  ats,
  tailored,
  approval,
  applicationResult,
  resume,
  onApprove,
  onReject,
}: {
  posting: JobPosting;
  ats?: ATSResult;
  tailored?: TailoredResume;
  approval?: ApprovalStatus;
  applicationResult?: ApplicationResult;
  resume: ParsedResume | null;
  onApprove: (postingId: string, decision: ApprovalDecision) => Promise<void>;
  onReject: (postingId: string, decision: ApprovalDecision) => Promise<void>;
}) {
  const [tab, setTab] = useState<Tab>("fit");

  return (
    <div className="animate-slide-up space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">{posting.title}</h2>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">{posting.company}</p>
          </div>
          {ats && <ScoreRing score={ats.score} size={56} />}
        </div>

        {tailored && tailored.faithfulness_status !== "passed" && tailored.faithfulness_status !== "pending" && (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700 dark:border-amber-900/50 dark:bg-amber-500/10 dark:text-amber-400">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <div>
              <p className="font-medium">Failed the faithfulness check ({tailored.faithfulness_status.replace("_", " ")})</p>
              {tailored.faithfulness_violations.slice(0, 3).map((v, i) => (
                <p key={i} className="mt-0.5 opacity-90">
                  {v}
                </p>
              ))}
            </div>
          </div>
        )}

        <div className="mt-4 flex gap-1 border-b border-slate-200 dark:border-slate-800">
          {(
            [
              ["fit", "ATS fit"],
              ["resume", "Tailored resume"],
              ["cover-letter", "Cover letter"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`relative px-3 py-2 text-sm font-medium transition-colors ${
                tab === key
                  ? "text-brand-600 dark:text-brand-400"
                  : "text-slate-400 hover:text-slate-600 dark:text-slate-500 dark:hover:text-slate-300"
              }`}
            >
              {label}
              {tab === key && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand-500 dark:bg-brand-400" />
              )}
            </button>
          ))}
        </div>

        <div className="mt-4">
          {tab === "fit" &&
            (ats ? (
              <div className="space-y-4">
                <p className="text-sm leading-relaxed text-slate-600 dark:text-slate-300">{ats.fit_rationale}</p>
                <SignalBars breakdown={ats.signal_breakdown} />
                {ats.missing_keywords.length > 0 && (
                  <div>
                    <p className="mb-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400">
                      Missing keywords
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {ats.missing_keywords.map((kw) => (
                        <span
                          key={kw}
                          className="rounded-full bg-rose-50 px-2.5 py-0.5 text-xs font-medium text-rose-600 dark:bg-rose-500/10 dark:text-rose-400"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-400 dark:text-slate-500">Not yet scored.</p>
            ))}

          {tab === "resume" &&
            (tailored ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                  <Sparkles className="h-3.5 w-3.5 text-brand-500 dark:text-brand-400" />
                  Only reordered / reworded from your real experience — nothing invented.
                </div>
                <DiffBullets bullets={tailored.bullets} resume={resume} />
              </div>
            ) : (
              <p className="text-sm text-slate-400 dark:text-slate-500">This posting didn't reach tailoring.</p>
            ))}

          {tab === "cover-letter" &&
            (tailored?.cover_letter ? (
              <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50/60 p-4 dark:border-slate-800 dark:bg-slate-900/50">
                <Mail className="mt-0.5 h-4 w-4 shrink-0 text-slate-400 dark:text-slate-500" />
                <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-slate-200">
                  {tailored.cover_letter}
                </p>
              </div>
            ) : (
              <p className="text-sm text-slate-400 dark:text-slate-500">No cover letter drafted.</p>
            ))}
        </div>
      </div>

      {ats?.passed_gate && tailored && (
        <ApprovalControls
          approval={approval}
          applicationResult={applicationResult}
          faithfulnessPassed={tailored.faithfulness_status === "passed"}
          onApprove={() => onApprove(posting.id, "approved")}
          onReject={() => onReject(posting.id, "rejected")}
        />
      )}

      {ats && !ats.passed_gate && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          This posting scored below the ATS gate ({Math.round(ats.score)} / 70) and wasn't tailored or
          sent for approval.
        </div>
      )}
      {ats?.passed_gate && !tailored && (
        <StatusPill tone="neutral">Waiting on the Tailor Agent…</StatusPill>
      )}
    </div>
  );
}
