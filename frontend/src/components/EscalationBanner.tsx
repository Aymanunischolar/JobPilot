import { AlertTriangle } from "lucide-react";

export function EscalationBanner({ reason }: { reason: string | null }) {
  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-500/10 dark:text-amber-300">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="font-semibold">Flagged for your review</p>
        <p className="mt-0.5 text-amber-700 dark:text-amber-400">
          {reason ?? "The Manager flagged an ambiguous case instead of guessing."}
        </p>
      </div>
    </div>
  );
}
