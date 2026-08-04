import { useRef, useState, type DragEvent } from "react";
import { UploadCloud, CheckCircle2, AlertTriangle } from "lucide-react";

const INGEST_STEPS = ["saved", "extracted", "embedded", "summarized", "proposed"] as const;
type IngestStep = (typeof INGEST_STEPS)[number];

export type IngestProgress =
  | { phase: "idle" }
  | { phase: "running"; completedSteps: Set<IngestStep>; currentStep: IngestStep | null; detail: string | null }
  | { phase: "done"; artifactId: number; deduped: boolean }
  | { phase: "error"; message: string };

interface IngestPanelProps {
  clientId: string;
  ingestProgress: IngestProgress;
  noteText: string;
  onNoteChange: (text: string) => void;
  onFileDrop: (e: DragEvent<HTMLDivElement>) => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onNoteSubmit: () => void;
}

export function IngestPanel({
  clientId,
  ingestProgress,
  noteText,
  onNoteChange,
  onFileDrop,
  onFileSelect,
  onNoteSubmit,
}: IngestPanelProps) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const running = ingestProgress.phase === "running";

  return (
    <div className="flex flex-col gap-4">
      {/* Drop zone */}
      <div
        className={[
          "border-2 border-dashed rounded-xl px-6 py-10 text-center transition-colors duration-150 flex flex-col items-center gap-3",
          dragOver
            ? "border-databricks-navy bg-[var(--color-databricks-cloud)] text-databricks-navy"
            : "border-[var(--color-border)] text-databricks-slate",
          !clientId
            ? "opacity-50 cursor-not-allowed"
            : "cursor-pointer hover:border-databricks-navy hover:text-databricks-navy",
        ].join(" ")}
        role="button"
        aria-label="Upload dossier artifact — drag a file here or click to select"
        tabIndex={clientId ? 0 : -1}
        onDragOver={(e) => {
          e.preventDefault();
          if (clientId) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          setDragOver(false);
          if (clientId) onFileDrop(e);
        }}
        onClick={() => {
          if (clientId) fileInputRef.current?.click();
        }}
        onKeyDown={(e) => {
          if (clientId && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
      >
        <UploadCloud className="w-8 h-8 opacity-60" aria-hidden="true" />
        <div className="text-sm font-medium">
          {clientId ? "Drop a file here, or click to select" : "Select a client to upload"}
        </div>
        <div className="text-xs">PDF, image, DOCX, text</div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif,.docx,.doc,.txt"
          aria-label="Select file to ingest"
          className="hidden"
          onChange={onFileSelect}
          disabled={!clientId}
        />
      </div>

      {/* Typed note */}
      <div className="flex flex-col gap-2">
        <label
          htmlFor="typed-note"
          className="text-xs font-medium uppercase tracking-wider text-databricks-slate"
        >
          Or paste a typed note
        </label>
        <textarea
          id="typed-note"
          className="w-full resize-y text-sm px-3 py-2 border border-[var(--color-border)] rounded-lg text-databricks-navy placeholder:text-databricks-slate focus:outline-none focus:border-databricks-navy/40 transition-colors duration-150"
          rows={3}
          value={noteText}
          onChange={(e) => onNoteChange(e.target.value)}
          disabled={!clientId || running}
          aria-label="Type a note to add to the dossier"
          placeholder={
            clientId
              ? "Meeting takeaway, idea, observation…"
              : "Select a client to add a note"
          }
        />
        <button
          type="button"
          className="self-start bg-databricks-red hover:bg-[#e02f1c] text-white font-medium text-sm px-3.5 py-1.5 rounded-md shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-databricks-red/30 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={onNoteSubmit}
          disabled={!clientId || !noteText.trim() || running}
          aria-label="Add typed note to dossier"
        >
          Add note
        </button>
      </div>

      {/* Progress */}
      {ingestProgress.phase !== "idle" && (
        <IngestProgressView progress={ingestProgress} />
      )}
    </div>
  );
}

export function IngestProgressView({ progress }: { progress: IngestProgress }) {
  if (progress.phase === "idle") return null;

  if (progress.phase === "error") {
    return (
      <div
        className="px-4 py-3 rounded-xl bg-red-50 border border-red-200 text-databricks-lava text-sm flex items-start gap-2"
        role="alert"
      >
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
        <div>
          <span className="font-semibold">Ingest failed:</span> {progress.message}
        </div>
      </div>
    );
  }

  if (progress.phase === "done") {
    return (
      <div
        className="px-4 py-3 rounded-xl bg-green-50 border border-green-200 text-databricks-moss text-sm flex items-center gap-2"
        role="status"
      >
        <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden="true" />
        {progress.deduped ? (
          <>Duplicate detected — artifact already in dossier (content hash matched).</>
        ) : (
          <>Artifact #{progress.artifactId} ingested successfully.</>
        )}
      </div>
    );
  }

  // phase === "running"
  const { completedSteps, currentStep, detail } = progress;
  return (
    <div
      className="px-4 py-3 rounded-xl bg-[var(--color-surface-muted)] border border-[var(--color-border)] text-sm"
      role="status"
      aria-live="polite"
    >
      <ul className="list-none m-0 p-0 flex flex-col gap-1.5" aria-label="Ingest pipeline progress">
        {INGEST_STEPS.map((step) => {
          const done = completedSteps.has(step);
          const active = currentStep === step && !done;
          return (
            <li
              key={step}
              className={[
                "flex items-center gap-2",
                done
                  ? "text-databricks-moss"
                  : active
                  ? "text-databricks-navy font-semibold"
                  : "text-databricks-slate",
              ].join(" ")}
              aria-label={`Step ${step}: ${done ? "complete" : active ? "in progress" : "pending"}`}
            >
              <span className="w-5 text-center text-sm font-bold shrink-0" aria-hidden="true">
                {done ? "✓" : active ? "…" : "○"}
              </span>
              <span className="capitalize">{step}</span>
              {done && detail && completedSteps.size === INGEST_STEPS.indexOf(step) + 1 && (
                <span className="text-xs text-databricks-slate font-normal">{detail}</span>
              )}
              {done && step === "summarized" && detail && (
                <span className="text-xs text-databricks-slate font-normal truncate max-w-48">
                  {detail}
                </span>
              )}
              {active && (
                <span
                  className="inline-block w-3.5 h-3.5 border-2 border-[var(--color-border)] border-t-databricks-red rounded-full ml-0.5"
                  style={{ animation: "spin 0.7s linear infinite" }}
                  aria-label="Loading"
                />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
