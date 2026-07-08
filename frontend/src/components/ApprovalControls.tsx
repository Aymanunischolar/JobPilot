import { Check, ExternalLink, Loader2, Send, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import type { ApplicationResult, ApprovalStatus } from "../types";
import { StatusPill } from "./StatusPill";

export function ApprovalControls({
  approval,
  applicationResult,
  faithfulnessPassed,
  onApprove,
  onReject,
}: {
  approval?: ApprovalStatus;
  applicationResult?: ApplicationResult;
  faithfulnessPassed: boolean;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
}) {
  const [pending, setPending] = useState<"approve" | "reject" | null>(null);

  const decision = approval?.decision ?? "pending";

  if (decision === "approved") {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4 dark:border-emerald-900/50 dark:bg-emerald-500/5">
        <div className="flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-400">
          <ShieldCheck className="h-4 w-4" />
          Approved{approval?.approved_by ? ` by ${approval.approved_by}` : ""}
        </div>
        {applicationResult ? (
          <div className="mt-3 space-y-1.5 border-t border-emerald-200/70 pt-3 text-xs dark:border-emerald-900/50">
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-600 dark:text-slate-300">Channel:</span>
              <StatusPill tone="brand">{applicationResult.channel.replace(/_/g, " ")}</StatusPill>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-600 dark:text-slate-300">Action:</span>
              <span className="text-slate-600 dark:text-slate-300">
                {applicationResult.action.replace(/_/g, " ")}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {applicationResult.auto_submitted ? (
                <StatusPill tone="success" icon={<Send className="h-3 w-3" />}>
                  Auto-submitted (allow-listed)
                </StatusPill>
              ) : (
                <StatusPill tone="warning">Form filled — your click required to submit</StatusPill>
              )}
            </div>
          </div>
        ) : (
          <p className="mt-2 flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400">
            <Loader2 className="h-3 w-3 animate-spin" /> Application Agent is processing…
          </p>
        )}
      </div>
    );
  }

  if (decision === "rejected") {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
        <X className="h-4 w-4" /> You rejected this posting — no application was submitted.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      {!faithfulnessPassed && (
        <p className="mb-3 text-xs text-amber-600 dark:text-amber-400">
          This draft hasn't passed the faithfulness check yet — review carefully before approving.
        </p>
      )}
      <div className="flex gap-2">
        <button
          disabled={pending !== null}
          onClick={async () => {
            setPending("approve");
            try {
              await onApprove();
            } finally {
              setPending(null);
            }
          }}
          className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending === "approve" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          Approve & apply
        </button>
        <button
          disabled={pending !== null}
          onClick={async () => {
            setPending("reject");
            try {
              await onReject();
            } finally {
              setPending(null);
            }
          }}
          className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          {pending === "reject" ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
          Reject
        </button>
      </div>
      <p className="mt-2.5 flex items-center gap-1 text-[11px] text-slate-400 dark:text-slate-500">
        <ExternalLink className="h-2.5 w-2.5" />
        Nothing is submitted anywhere until you approve — this is the human approval gate.
      </p>
    </div>
  );
}
