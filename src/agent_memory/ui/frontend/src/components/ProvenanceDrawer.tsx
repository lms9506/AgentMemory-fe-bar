import { X, ArrowUpRight } from "lucide-react";
import { type Artifact, formatTs, rawArtifactUrl } from "../api";

interface ProvenanceDrawerProps {
  artifact: Artifact | null;
  loading: boolean;
  onClose: () => void;
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null;
  return (
    <>
      <dt className="text-xs font-medium uppercase tracking-wider text-databricks-slate mt-3 first:mt-0">
        {label}
      </dt>
      <dd className="text-sm text-databricks-navy mt-0.5 leading-relaxed">{value}</dd>
    </>
  );
}

export function ProvenanceDrawer({ artifact, loading, onClose }: ProvenanceDrawerProps) {
  if (!loading && !artifact) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 z-40"
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Drawer */}
      <aside
        className="fixed right-0 top-0 h-full w-96 max-w-[90vw] bg-white z-50 flex flex-col shadow-2xl border-l border-[var(--color-border)]"
        role="complementary"
        aria-label="Artifact provenance details"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)] border-t-2 border-t-databricks-navy">
          <h2 className="text-base font-semibold text-databricks-navy">
            {loading ? "Loading…" : `Artifact #${artifact?.artifact_id}`}
          </h2>
          <button
            type="button"
            className="p-1.5 rounded-md text-databricks-slate hover:text-databricks-navy hover:bg-[var(--color-databricks-cloud)] transition-colors duration-150"
            onClick={onClose}
            aria-label="Close provenance panel"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="flex flex-col gap-3" aria-label="Loading provenance">
              {[120, 80, 200, 160].map((w, i) => (
                <div key={i} className="skeleton h-4 rounded" style={{ width: `${w}px` }} />
              ))}
            </div>
          ) : artifact ? (
            <>
              <dl className="m-0">
                <Row label="Filename" value={artifact.original_filename} />
                <Row label="Kind" value={artifact.kind} />
                <Row label="Ingested" value={formatTs(artifact.ingested_at)} />
                <Row label="Summary" value={artifact.summary} />
                {artifact.extracted_text && (
                  <>
                    <dt className="text-xs font-medium uppercase tracking-wider text-databricks-slate mt-3">
                      Extracted text
                    </dt>
                    <dd className="mt-1 text-xs text-databricks-slate leading-relaxed max-h-48 overflow-y-auto bg-[var(--color-surface-muted)] rounded-lg px-3 py-2 font-mono whitespace-pre-wrap break-words">
                      {artifact.extracted_text}
                    </dd>
                  </>
                )}
                {artifact.sensitivity_tags.length > 0 && (
                  <>
                    <dt className="text-xs font-medium uppercase tracking-wider text-databricks-slate mt-3">
                      Sensitivity
                    </dt>
                    <dd className="mt-1 flex flex-wrap gap-1">
                      {artifact.sensitivity_tags.map((tag) => (
                        <span
                          key={tag}
                          className="text-[0.68rem] font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200"
                        >
                          {tag}
                        </span>
                      ))}
                    </dd>
                  </>
                )}
              </dl>

              <div className="mt-5 pt-4 border-t border-[var(--color-border)]">
                <a
                  href={rawArtifactUrl(artifact.artifact_id)}
                  download={artifact.original_filename}
                  className="inline-flex items-center gap-1.5 bg-databricks-red hover:bg-[#e02f1c] text-white font-medium text-sm px-3.5 py-1.5 rounded-md shadow-sm transition-colors duration-150 no-underline"
                  aria-label={`Download raw file ${artifact.original_filename}`}
                >
                  Download original
                  <ArrowUpRight className="w-3.5 h-3.5" aria-hidden="true" />
                </a>
              </div>
            </>
          ) : null}
        </div>
      </aside>
    </>
  );
}
