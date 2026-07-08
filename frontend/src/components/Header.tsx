import { Moon, RotateCcw, Sun } from "lucide-react";
import { useTheme } from "../hooks/useTheme";

export function Header({ onReset, showReset }: { onReset: () => void; showReset: boolean }) {
  const { theme, toggle } = useTheme();

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/80 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/80">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm shadow-brand-500/30">
            <svg viewBox="0 0 32 32" fill="none" className="h-4.5 w-4.5">
              <path
                d="M16 6L18.5 13.5L26 16L18.5 18.5L16 26L13.5 18.5L6 16L13.5 13.5L16 6Z"
                fill="currentColor"
              />
            </svg>
          </div>
          <div>
            <p className="text-sm font-bold tracking-tight text-slate-900 dark:text-white">JobPilot</p>
            <p className="hidden text-[11px] leading-none text-slate-400 dark:text-slate-500 sm:block">
              Human-approved job applications
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {showReset && (
            <button
              onClick={onReset}
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">New session</span>
            </button>
          )}
          <button
            onClick={toggle}
            aria-label="Toggle theme"
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </header>
  );
}
