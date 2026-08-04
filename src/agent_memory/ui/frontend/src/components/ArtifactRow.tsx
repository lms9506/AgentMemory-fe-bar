import { FileText, FileType2, Image, PenLine, File, ChevronRight, CheckCircle2, ArrowUpRight } from "lucide-react";
import { type Artifact, formatTs, rawArtifactUrl } from "../api";

const KIND_ICON = {
  text: FileText,
  pdf: FileType2,
  image: Image,
  handwritten: PenLine,
  other: File,
  docx: File,
} as const;

const KIND_BADGE: Record<string, string> = {
  text: "bg-blue-50 text-blue-700",
  pdf: "bg-red-50 text-databricks-lava",
  image: "bg-green-50 text-databricks-moss",
  docx: "bg-purple-50 text-purple-700",
  handwritten: "bg-amber-50 text-amber-700",
  other: "bg-[var(--color-surface-muted)] text-databricks-slate",
};

interface ArtifactRowProps {
  artifact: Artifact;
  onOpen?: (artifact: Artifact) => void;
  compact?: boolean;
}

export function ArtifactRow({ artifact: a, onOpen, compact }: ArtifactRowProps) {
  const Icon = KIND_ICON[a.kind as keyof typeof KIND_ICON] ?? File;
  const badgeCls = KIND_BADGE[a.kind] ?? "bg-[var(--color-surface-muted)] text-databricks-slate";

  return (
    <div className="flex items-start gap-3 px-4 py-3 rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] hover:border-[var(--color-border-strong)] transition-colors duration-150">
      {/* Kind icon */}
      <span className={`shrink-0 mt-0.5 p-1.5 rounded-lg ${badgeCls}`} aria-hidden="true">
        <Icon className="w-3.5 h-3.5" />
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span
            className="text-sm font-medium text-databricks-navy truncate"
            title={a.original_filename}
          >
            {a.original_filename}
          </span>
          <span className="text-xs text-databricks-slate shrink-0">{formatTs(a.ingested_at)}</span>
        </div>

        {!compact && a.summary && (
          <p className="text-xs text-databricks-slate leading-relaxed mt-1 line-clamp-2">
            {a.summary}
          </p>
        )}

        <div className="flex items-center gap-3 mt-1.5 flex-wrap">
          {a.contributed_to_profile && (
            <span
              className="inline-flex items-center gap-1 text-[0.68rem] font-medium px-1.5 py-0.5 rounded-full bg-green-50 text-databricks-moss"
              title="Used in the current profile distillation"
            >
              <CheckCircle2 className="w-3 h-3" aria-hidden="true" />
              In profile
            </span>
          )}
          <a
            href={rawArtifactUrl(a.artifact_id)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 text-xs text-databricks-slate hover:text-databricks-navy transition-colors duration-150"
            aria-label={`Open original file ${a.original_filename}`}
          >
            Original
            <ArrowUpRight className="w-3 h-3" aria-hidden="true" />
          </a>
        </div>
      </div>

      {/* Open button */}
      {onOpen && (
        <button
          type="button"
          className="shrink-0 p-1 rounded text-databricks-slate hover:text-databricks-navy hover:bg-[var(--color-databricks-cloud)] transition-colors duration-150"
          onClick={() => onOpen(a)}
          aria-label={`Open provenance for ${a.original_filename}`}
        >
          <ChevronRight className="w-4 h-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
