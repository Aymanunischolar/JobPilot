import { Briefcase, GraduationCap, Mail, User } from "lucide-react";
import type { ParsedResume } from "../types";

export function ResumeSummary({ resume }: { resume: ParsedResume }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-2.5">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-brand-600 dark:bg-brand-500/15 dark:text-brand-400">
          <User className="h-4.5 w-4.5" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">
            {resume.full_name ?? "Your resume"}
          </p>
          {resume.email && (
            <p className="flex items-center gap-1 truncate text-xs text-slate-500 dark:text-slate-400">
              <Mail className="h-3 w-3 shrink-0" />
              {resume.email}
            </p>
          )}
        </div>
      </div>

      {resume.roles.length > 0 && (
        <div className="mt-4">
          <p className="mb-1.5 flex items-center gap-1 text-xs font-semibold text-slate-500 dark:text-slate-400">
            <Briefcase className="h-3 w-3" /> Most recent role
          </p>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {resume.roles[0].title} · {resume.roles[0].company}
          </p>
        </div>
      )}

      {resume.education.length > 0 && (
        <div className="mt-3">
          <p className="mb-1.5 flex items-center gap-1 text-xs font-semibold text-slate-500 dark:text-slate-400">
            <GraduationCap className="h-3 w-3" /> Education
          </p>
          <p className="text-sm text-slate-700 dark:text-slate-200">
            {resume.education[0].degree ? `${resume.education[0].degree}, ` : ""}
            {resume.education[0].institution}
          </p>
        </div>
      )}

      {resume.skills.length > 0 && (
        <div className="mt-4">
          <p className="mb-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400">Skills</p>
          <div className="flex flex-wrap gap-1.5">
            {resume.skills.slice(0, 12).map((skill) => (
              <span
                key={skill}
                className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              >
                {skill}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
