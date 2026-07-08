import type { ApprovalDecision, Channel, JobState } from "../types";

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function uploadResume(file: File): Promise<JobState> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/resume/upload`, { method: "POST", body: form });
  return handle<JobState>(res);
}

export async function getSession(sessionId: string): Promise<JobState> {
  const res = await fetch(`${BASE}/sessions/${sessionId}`);
  return handle<JobState>(res);
}

export async function submitApproval(
  sessionId: string,
  postingId: string,
  decision: ApprovalDecision,
  approvedBy?: string,
  channel?: Channel | null,
): Promise<JobState> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/approvals`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      posting_id: postingId,
      decision,
      approved_by: approvedBy ?? null,
      channel: channel ?? null,
    }),
  });
  return handle<JobState>(res);
}

export async function getTrace(traceId: string): Promise<JobState> {
  const res = await fetch(`${BASE}/trace/${traceId}`);
  return handle<JobState>(res);
}
