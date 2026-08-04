import { UploadCloud, MessageSquare } from "lucide-react";
import { type ClientInfo } from "../api";
import { ClientCombobox } from "./ClientCombobox";

interface ClientBannerProps {
  clients: ClientInfo[];
  clientId: string;
  onClientChange: (id: string) => void;
  artifactCount: number;
  pendingCount: number;
  activeTab: string;
  onTabAction: (action: "ingest" | "brainstorm") => void;
}

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export function ClientBanner({
  clients,
  clientId,
  onClientChange,
  artifactCount,
  pendingCount,
  activeTab,
  onTabAction,
}: ClientBannerProps) {
  const current = clients.find((c) => c.id === clientId);
  const displayName = current?.display_name ?? clientId;

  return (
    <div className="sticky top-12 z-40 bg-[var(--color-surface-muted)] border-b border-[var(--color-border)] px-6 py-3">
      <div className="max-w-screen-xl mx-auto flex flex-wrap items-center gap-4">
        {/* Avatar + name */}
        <div className="flex items-center gap-3 min-w-0">
          {clientId ? (
            <span
              className="w-9 h-9 rounded-full bg-gradient-to-br from-databricks-navy to-databricks-red flex items-center justify-center text-sm font-bold text-white shrink-0"
              aria-hidden="true"
            >
              {initials(displayName)}
            </span>
          ) : (
            <span className="w-9 h-9 rounded-full bg-[var(--color-border)] shrink-0" aria-hidden="true" />
          )}
          <div className="min-w-0">
            <h1 className="text-base font-semibold text-databricks-navy leading-tight truncate">
              {clientId ? displayName : "No client selected"}
            </h1>
            {clientId && (
              <p className="text-xs text-databricks-slate leading-tight mt-0.5">
                {artifactCount} artifact{artifactCount !== 1 ? "s" : ""}
                {pendingCount > 0 && (
                  <>
                    {" · "}
                    <span className="text-databricks-orange font-medium">
                      {pendingCount} pending
                    </span>
                  </>
                )}
              </p>
            )}
          </div>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Compact "Switch client" chip — banner already shows the current client identity */}
        <ClientCombobox clients={clients} clientId={clientId} onSelect={onClientChange} compact />

        {/* Contextual CTAs */}
        {clientId && (activeTab === "timeline" || activeTab === "overview") && (
          <button
            type="button"
            className="flex items-center gap-1.5 bg-databricks-red hover:bg-[#e02f1c] text-white font-medium text-sm px-3.5 py-1.5 rounded-md shadow-sm transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-databricks-red/30"
            onClick={() => onTabAction("ingest")}
            aria-label="Ingest a new artifact"
          >
            <UploadCloud className="w-4 h-4" aria-hidden="true" />
            Ingest artifact
          </button>
        )}
        {clientId && (activeTab === "brainstorm" || activeTab === "overview") && (
          <button
            type="button"
            className="flex items-center gap-1.5 border border-databricks-navy/20 text-databricks-navy hover:bg-[var(--color-databricks-cloud)] text-sm font-medium px-3.5 py-1.5 rounded-md transition-colors duration-150"
            onClick={() => onTabAction("brainstorm")}
            aria-label="Start a brainstorm session"
          >
            <MessageSquare className="w-4 h-4" aria-hidden="true" />
            Brainstorm
          </button>
        )}
      </div>
    </div>
  );
}
