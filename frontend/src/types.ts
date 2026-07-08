// Mirrors backend/app/schemas/models.py. Keep in sync with the Pydantic
// contracts — this is the same JobState shape the Manager Agent threads
// through the LangGraph pipeline (architecture doc §5).

export interface Bullet {
  id: string;
  text: string;
  quantified_metrics: string[];
}

export interface RoleExperience {
  title: string;
  company: string;
  start_date: string | null;
  end_date: string | null;
  bullets: Bullet[];
}

export interface Education {
  institution: string;
  degree: string | null;
  field_of_study: string | null;
  graduation_date: string | null;
}

export interface ParsedResume {
  full_name: string | null;
  email: string | null;
  phone: string | null;
  skills: string[];
  roles: RoleExperience[];
  education: Education[];
  certifications: string[];
  raw_text_hash: string;
}

export interface JobPosting {
  id: string;
  source_url: string;
  canonical_url: string;
  jd_text: string;
  jd_hash: string;
  company: string;
  title: string;
  relevance_score: number;
}

export interface ATSSignalBreakdown {
  keyword_coverage: number;
  title_seniority_alignment: number;
  experience_match: number;
  education_match: number;
  formatting_compatibility: number;
}

export interface ATSResult {
  score: number;
  missing_keywords: string[];
  fit_rationale: string;
  passed_gate: boolean;
  signal_breakdown: ATSSignalBreakdown;
}

export interface TailoredBullet {
  source_bullet_id: string;
  text: string;
  keywords_surfaced: string[];
}

export type FaithfulnessStatus = "pending" | "passed" | "failed_structural" | "failed_semantic";

export interface TailoredResume {
  bullets: TailoredBullet[];
  cover_letter: string;
  diff_summary: string;
  faithfulness_status: FaithfulnessStatus;
  faithfulness_violations: string[];
}

export type Channel = "career_page_allowlisted" | "major_job_board" | "email";
export type ApprovalDecision = "pending" | "approved" | "rejected";

export interface ApprovalStatus {
  decision: ApprovalDecision;
  channel: Channel | null;
  approved_by: string | null;
  decided_at: string | null;
}

export interface ApplicationResult {
  posting_id: string;
  channel: string;
  action: string;
  auto_submitted: boolean;
  cover_letter?: string;
}

export interface TraceEvent {
  trace_id: string;
  agent: string;
  input_hash: string;
  output_hash: string;
  decision: string;
  rationale: string;
  latency_ms: number;
  timestamp: number;
}

export interface JobState {
  session_id: string;
  trace_id: string;
  parsed_resume: ParsedResume | null;
  postings: JobPosting[];
  ats_results: Record<string, ATSResult>;
  tailored: Record<string, TailoredResume>;
  approvals: Record<string, ApprovalStatus>;
  application_results: Record<string, ApplicationResult>;
  trace: TraceEvent[];
  current_step: string;
  escalated: boolean;
  escalation_reason: string | null;
}
