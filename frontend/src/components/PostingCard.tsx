import clsx from "clsx";
import { Building2, ChevronRight, ExternalLink } from "lucide-react";
import type { ATSResult, JobPosting, TailoredResume } from "../types";
import { ScoreRing } from "./ScoreRing";
import { StatusPill } from "./StatusPill";

export function PostingCard({
  posting,
  ats,
  tailored,
  selected,
  onSelect,
}: {
  posting: JobPosting;
  ats?: ATSResult;
  tailored?: TailoredResume;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={clsx(
        "w-full rounded-xl border p-4 text-left transition-all duration-150",
        selected
          ? "border-brand-400 bg-brand-50/60 ring-1 ring-brand-400 dark:border-brand-500 dark:bg-brand-500/10"
          : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700",
      )}
    >
      <div className="flex items-start gap-3">
        {ats && <ScoreRing score={ats.score} size={48} />}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{posting.title}</p>
          <p className="mt-0.5 flex items-center gap-1 truncate text-xs text-slate-500 dark:text-slate-400">
            <Building2 className="h-3 w-3 shrink-0" />
            {posting.company || "Unknown company"}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {ats ? (
              <StatusPill tone={ats.passed_gate ? "success" : "danger"}>
                {ats.passed_gate ? "Passes ATS gate" : "Below ATS gate"}
              </StatusPill>
            ) : (
              <StatusPill tone="neutral">Not scored</StatusPill>
            )}
            {tailored && (
              <StatusPill
                tone={
                  tailored.faithfulness_status === "passed"
                    ? "brand"
                    : tailored.faithfulness_status === "pending"
                      ? "neutral"
                      : "warning"
                }
              >
                {tailored.faithfulness_status === "passed"
                  ? "Tailored"
                  : tailored.faithfulness_status === "pending"
                    ? "Tailoring…"
                    : "Needs review"}
              </StatusPill>
            )}
          </div>
        </div>
        <ChevronRight
          className={clsx(
            "mt-1 h-4 w-4 shrink-0 text-slate-300 transition-transform dark:text-slate-600",
            selected && "translate-x-0.5 text-brand-500 dark:text-brand-400",
          )}
        />
      </div>
      <a
        href={posting.source_url}
        target="_blank"
        rel="noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="mt-2 inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-brand-600 dark:text-slate-500 dark:hover:text-brand-400"
      >
        View original posting <ExternalLink className="h-2.5 w-2.5" />
      </a>
    </button>
  );
}
