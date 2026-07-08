import { ArrowRight } from "lucide-react";
import type { ParsedResume, TailoredBullet } from "../types";

function buildBulletIndex(resume: ParsedResume | null): Map<string, string> {
  const map = new Map<string, string>();
  if (!resume) return map;
  for (const role of resume.roles) {
    for (const bullet of role.bullets) {
      map.set(bullet.id, bullet.text);
    }
  }
  return map;
}

export function DiffBullets({
  bullets,
  resume,
}: {
  bullets: TailoredBullet[];
  resume: ParsedResume | null;
}) {
  const originals = buildBulletIndex(resume);

  if (bullets.length === 0) {
    return <p className="text-sm text-slate-400 dark:text-slate-500">No tailored bullets yet.</p>;
  }

  return (
    <ul className="space-y-3">
      {bullets.map((bullet, i) => {
        const original = originals.get(bullet.source_bullet_id);
        const changed = original !== undefined && original.trim() !== bullet.text.trim();

        return (
          <li
            key={`${bullet.source_bullet_id}-${i}`}
            className="rounded-lg border border-slate-200 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-900/50"
          >
            {changed ? (
              <div className="space-y-1.5">
                <p className="text-xs leading-relaxed text-slate-400 line-through decoration-rose-400/70 dark:text-slate-500">
                  {original}
                </p>
                <div className="flex items-start gap-1.5">
                  <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-500 dark:text-brand-400" />
                  <p className="text-sm leading-relaxed text-slate-800 dark:text-slate-100">{bullet.text}</p>
                </div>
              </div>
            ) : (
              <p className="text-sm leading-relaxed text-slate-800 dark:text-slate-100">{bullet.text}</p>
            )}
            {bullet.keywords_surfaced.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {bullet.keywords_surfaced.map((kw) => (
                  <span
                    key={kw}
                    className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                  >
                    {kw}
                  </span>
                ))}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
