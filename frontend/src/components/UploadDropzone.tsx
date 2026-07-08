import clsx from "clsx";
import { FileText, UploadCloud } from "lucide-react";
import { useCallback, useRef, useState } from "react";

const ACCEPTED = [".pdf", ".docx", ".doc"];

function isAccepted(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED.some((ext) => name.endsWith(ext));
}

export function UploadDropzone({ onFile }: { onFile: (file: File) => void }) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;
      if (!isAccepted(file)) {
        setError("Only PDF and DOCX resumes are supported.");
        return;
      }
      setError(null);
      onFile(file);
    },
    [onFile],
  );

  return (
    <div className="w-full">
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        className={clsx(
          "group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-16 text-center transition-all duration-200",
          isDragging
            ? "scale-[1.01] border-brand-500 bg-brand-50 dark:border-brand-400 dark:bg-brand-500/10"
            : "border-slate-300 bg-white hover:border-brand-400 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-brand-500 dark:hover:bg-slate-800/50",
        )}
      >
        <div
          className={clsx(
            "mb-4 flex h-14 w-14 items-center justify-center rounded-full transition-colors",
            isDragging
              ? "bg-brand-500 text-white"
              : "bg-slate-100 text-slate-400 group-hover:bg-brand-100 group-hover:text-brand-600 dark:bg-slate-800 dark:text-slate-500 dark:group-hover:bg-brand-500/20 dark:group-hover:text-brand-400",
          )}
        >
          {isDragging ? <FileText className="h-6 w-6" /> : <UploadCloud className="h-6 w-6" />}
        </div>
        <p className="text-sm font-semibold text-slate-900 dark:text-white">
          {isDragging ? "Drop your resume here" : "Drag & drop your resume"}
        </p>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          or <span className="font-medium text-brand-600 dark:text-brand-400">browse files</span> — PDF or DOCX
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.doc"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {error && <p className="mt-3 text-center text-sm text-rose-600 dark:text-rose-400">{error}</p>}
    </div>
  );
}
