import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

const STEPS = [
  "Parsing your resume",
  "Searching for matching roles",
  "Scoring ATS fit for each posting",
  "Tailoring resumes & cover letters",
  "Checking every bullet for faithfulness",
  "Preparing for your review",
];

// Rough per-step durations that add up to roughly the pipeline's typical
// run time — the backend doesn't stream progress, so this approximates
// it. Caps at the last step and waits there until the response returns.
const STEP_DURATIONS_MS = [1800, 2600, 6000, 6000, 4000, Infinity];

export function PipelineLoader() {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (stepIndex >= STEPS.length - 1) return;
    const timer = setTimeout(() => setStepIndex((i) => i + 1), STEP_DURATIONS_MS[stepIndex]);
    return () => clearTimeout(timer);
  }, [stepIndex]);

  return (
    <div className="mx-auto w-full max-w-md animate-fade-in">
      <div className="mb-8 flex justify-center">
        <div className="relative flex h-16 w-16 items-center justify-center">
          <div className="absolute inset-0 animate-ping rounded-full bg-brand-400/30" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-lg shadow-brand-500/30">
            <Loader2 className="h-7 w-7 animate-spin" />
          </div>
        </div>
      </div>

      <ol className="space-y-3">
        {STEPS.map((step, i) => {
          const done = i < stepIndex;
          const active = i === stepIndex;
          return (
            <li
              key={step}
              className="flex items-center gap-3 rounded-xl border border-slate-200/70 bg-white px-4 py-3 transition-all duration-300 dark:border-slate-800 dark:bg-slate-900"
              style={{ opacity: done || active ? 1 : 0.4 }}
            >
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs ${
                  done
                    ? "bg-emerald-500 text-white"
                    : active
                      ? "bg-brand-500 text-white"
                      : "bg-slate-200 dark:bg-slate-700"
                }`}
              >
                {done ? <Check className="h-3 w-3" /> : active ? <span className="h-1.5 w-1.5 animate-pulse-slow rounded-full bg-white" /> : null}
              </span>
              <span
                className={`text-sm ${
                  done || active
                    ? "font-medium text-slate-800 dark:text-slate-200"
                    : "text-slate-400 dark:text-slate-600"
                }`}
              >
                {step}
              </span>
            </li>
          );
        })}
      </ol>

      <p className="mt-6 text-center text-xs text-slate-400 dark:text-slate-500">
        This can take up to a minute — the Manager is running search, scoring,
        tailoring, and a hallucination check before anything reaches you.
      </p>
    </div>
  );
}
