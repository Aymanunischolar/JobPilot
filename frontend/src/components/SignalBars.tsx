import type { ATSSignalBreakdown } from "../types";

const SIGNALS: { key: keyof ATSSignalBreakdown; label: string; weight: string }[] = [
  { key: "keyword_coverage", label: "Keyword coverage", weight: "40%" },
  { key: "title_seniority_alignment", label: "Title / seniority", weight: "20%" },
  { key: "experience_match", label: "Experience match", weight: "15%" },
  { key: "education_match", label: "Education / certs", weight: "10%" },
  { key: "formatting_compatibility", label: "Formatting", weight: "15%" },
];

export function SignalBars({ breakdown }: { breakdown: ATSSignalBreakdown }) {
  return (
    <div className="space-y-2.5">
      {SIGNALS.map(({ key, label, weight }) => {
        const value = breakdown[key] ?? 0;
        return (
          <div key={key}>
            <div className="mb-1 flex items-baseline justify-between text-xs">
              <span className="font-medium text-slate-600 dark:text-slate-300">
                {label} <span className="text-slate-400 dark:text-slate-500">({weight})</span>
              </span>
              <span className="tabular-nums text-slate-500 dark:text-slate-400">{Math.round(value)}</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className="h-full rounded-full bg-brand-500 transition-[width] duration-500 ease-out dark:bg-brand-400"
                style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
