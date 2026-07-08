function toneForScore(score: number): { ring: string; text: string } {
  if (score >= 70) return { ring: "stroke-emerald-500", text: "text-emerald-600 dark:text-emerald-400" };
  if (score >= 55) return { ring: "stroke-amber-500", text: "text-amber-600 dark:text-amber-400" };
  return { ring: "stroke-rose-500", text: "text-rose-600 dark:text-rose-400" };
}

export function ScoreRing({ score, size = 64 }: { score: number; size?: number }) {
  const stroke = size * 0.11;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.min(100, Math.max(0, score)) / 100);
  const { ring, text } = toneForScore(score);

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          className="fill-none stroke-slate-200 dark:stroke-slate-700"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className={`fill-none transition-[stroke-dashoffset] duration-700 ease-out ${ring}`}
        />
      </svg>
      <div className={`absolute inset-0 flex items-center justify-center text-sm font-bold ${text}`}>
        {Math.round(score)}
      </div>
    </div>
  );
}
