import { type DragEvent } from "react";
import { Clock } from "lucide-react";
import { type Artifact, type Health } from "../api";
import { IngestPanel, type IngestProgress } from "./IngestPanel";
import { ArtifactRow } from "./ArtifactRow";
import { EmptyState } from "./EmptyState";

interface TimelineTabProps {
  clientId: string;
  artifacts: Artifact[];
  ingestProgress: IngestProgress;
  noteText: string;
  storage: Health | null;
  onNoteChange: (text: string) => void;
  onFileDrop: (e: DragEvent<HTMLDivElement>) => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onNoteSubmit: () => void;
  onOpenArtifact: (artifact: Artifact) => void;
}

export function TimelineTab({
  clientId,
  artifacts,
  ingestProgress,
  noteText,
  storage,
  onNoteChange,
  onFileDrop,
  onFileSelect,
  onNoteSubmit,
  onOpenArtifact,
}: TimelineTabProps) {
  return (
    <div className="flex flex-col gap-4">
      {/* Ingest card */}
      <div className="rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] border-t-2 border-t-databricks-navy overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-base font-semibold text-databricks-navy">Ingest artifact</h2>
        </div>
        <div className="px-4 py-4">
          <IngestPanel
            clientId={clientId}
            ingestProgress={ingestProgress}
            noteText={noteText}
            onNoteChange={onNoteChange}
            onFileDrop={onFileDrop}
            onFileSelect={onFileSelect}
            onNoteSubmit={onNoteSubmit}
          />
        </div>
      </div>

      {/* Timeline list card */}
      <div className="rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] border-t-2 border-t-databricks-navy overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="text-base font-semibold text-databricks-navy">
            Artifact timeline
            {artifacts.length > 0 && (
              <span className="ml-2 text-xs font-normal text-databricks-slate">
                {artifacts.length} item{artifacts.length !== 1 ? "s" : ""}, newest first
              </span>
            )}
          </h2>
        </div>
        <div className="px-4 py-4">
          {!clientId ? (
            <EmptyState icon={Clock} text="Select a client to view their dossier." />
          ) : artifacts.length === 0 ? (
            <EmptyState icon={Clock} text="No artifacts yet — upload the first one above." />
          ) : (
            <div className="flex flex-col gap-2">
              <ul className="list-none m-0 p-0 flex flex-col gap-2" aria-label="Dossier artifacts">
                {artifacts.map((a) => (
                  <li key={a.artifact_id}>
                    <ArtifactRow artifact={a} onOpen={onOpenArtifact} />
                  </li>
                ))}
              </ul>

              {/* Storage info */}
              {storage && (
                <p className="mt-2 pt-3 border-t border-dashed border-[var(--color-border)] text-xs text-databricks-slate">
                  Stored in —{" "}
                  {storage.workspace_url && storage.uc_catalog ? (
                    <a
                      className="underline decoration-dotted hover:decoration-solid text-databricks-slate"
                      href={`${storage.workspace_url}/explore/data/volumes/${storage.uc_catalog}/${storage.uc_schema}/${storage.volume_name}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label="Open UC Volume in Databricks workspace"
                    >
                      UC Volume{" "}
                      <code className="bg-[var(--color-surface-muted)] px-1 py-0.5 rounded text-[0.68rem]">
                        {storage.volume_name}
                      </code>
                    </a>
                  ) : (
                    <span>
                      UC Volume{" "}
                      <code className="bg-[var(--color-surface-muted)] px-1 py-0.5 rounded text-[0.68rem]">
                        {storage.volume_name ?? "dossier_raw"}
                      </code>
                    </span>
                  )}{" "}
                  (originals) · Lakebase{" "}
                  <code className="bg-[var(--color-surface-muted)] px-1 py-0.5 rounded text-[0.68rem]">
                    artifacts
                  </code>
                  ,{" "}
                  <code className="bg-[var(--color-surface-muted)] px-1 py-0.5 rounded text-[0.68rem]">
                    artifact_chunks
                  </code>{" "}
                  (transcripts &amp; summaries)
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

