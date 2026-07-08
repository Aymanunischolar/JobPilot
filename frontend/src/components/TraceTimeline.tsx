import clsx from "clsx";
import { Activity } from "lucide-react";
import type { TraceEvent } from "../types";

const DECISION_TONE: Record<string, string> = {
  pass: "bg-emerald-500",
  reject: "bg-rose-500",
  escalate: "bg-amber-500",
  passed: "bg-emerald-500",
  failed_structural: "bg-rose-500",
  failed_semantic: "bg-rose-500",
  drafted: "bg-brand-500",
  ok: "bg-slate-400",
  no_results: "bg-amber-500",
};

export function TraceTimeline({ events }: { events: TraceEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-slate-400 dark:text-slate-500">No trace events recorded yet.</p>;
  }

  return (
    <div className="scroll-thin max-h-80 space-y-0 overflow-y-auto pr-1">
      {events.map((event, i) => (
        <div key={i} className="flex gap-3 pb-4 last:pb-0">
          <div className="flex flex-col items-center">
            <span
              className={clsx(
                "mt-1 h-2 w-2 shrink-0 rounded-full",
                DECISION_TONE[event.decision] ?? "bg-slate-400",
              )}
            />
            {i < events.length - 1 && <span className="mt-1 w-px flex-1 bg-slate-200 dark:bg-slate-800" />}
          </div>
          <div className="min-w-0 pb-1">
            <div className="flex items-center gap-2">
              <Activity className="h-3 w-3 text-slate-400 dark:text-slate-500" />
              <span className="text-xs font-semibold capitalize text-slate-700 dark:text-slate-200">
                {event.agent.replace(/_/g, " ")}
              </span>
              <span className="text-[10px] text-slate-400 dark:text-slate-500">
                {event.latency_ms < 1000
                  ? `${Math.round(event.latency_ms)}ms`
                  : `${(event.latency_ms / 1000).toFixed(1)}s`}
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              <span className="font-medium capitalize">{event.decision.replace(/_/g, " ")}</span>
              {event.rationale ? ` — ${event.rationale}` : ""}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
