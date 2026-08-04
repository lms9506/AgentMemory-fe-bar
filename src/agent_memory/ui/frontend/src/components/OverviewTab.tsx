import { Clock, User, Sparkles, ArrowUpRight } from "lucide-react";
import { type Artifact, type ClientProfile, type Proposal, formatTs } from "../api";
import { ArtifactRow } from "./ArtifactRow";
import { EmptyState } from "./EmptyState";
import { type TabId } from "./TabBar";

interface OverviewTabProps {
  artifacts: Artifact[];
  profile: ClientProfile | null;
  proposals: Proposal[];
  clientId: string;
  onNavigate: (tab: TabId) => void;
  onOpenArtifact: (artifact: Artifact) => void;
}

function Card({
  title,
  badge,
  rightAction,
  children,
}: {
  title: string;
  badge?: number;
  rightAction?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] flex flex-col border-t-2 border-t-databricks-navy overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-databricks-navy">{title}</h2>
          {badge != null && badge > 0 && (
            <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-databricks-red text-white text-[0.65rem] font-bold">
              {badge}
            </span>
          )}
        </div>
        {rightAction}
      </div>
      <div className="flex-1 px-4 py-4">{children}</div>
    </div>
  );
}

function ProfileField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 py-2 border-b border-[var(--color-border)] last:border-0">
      <span className="text-xs font-medium uppercase tracking-wider text-databricks-slate">
        {label}
      </span>
      <span className="text-sm text-databricks-navy leading-relaxed">{value || "—"}</span>
    </div>
  );
}

export function OverviewTab({
  artifacts,
  profile,
  proposals,
  clientId,
  onNavigate,
  onOpenArtifact,
}: OverviewTabProps) {
  const recent = artifacts.slice(0, 5);
  const pendingProposals = proposals.slice(0, 3);

  return (
    <div className="flex flex-col gap-4">
      {/* Top row: recent activity + profile */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Recent activity — span 2 */}
        <div className="md:col-span-2">
          <Card
            title="Recent activity"
            rightAction={
              <button
                type="button"
                className="text-xs font-medium text-databricks-slate hover:text-databricks-navy flex items-center gap-0.5 transition-colors duration-150"
                onClick={() => onNavigate("timeline")}
                aria-label="See full timeline"
              >
                See full timeline
                <ArrowUpRight className="w-3 h-3" aria-hidden="true" />
              </button>
            }
          >
            {!clientId ? (
              <EmptyState icon={Clock} text="Select a client to view recent activity." />
            ) : recent.length === 0 ? (
              <EmptyState
                icon={Clock}
                text="No artifacts yet — upload the first one."
                ctaLabel="Go to Timeline"
                onCta={() => onNavigate("timeline")}
              />
            ) : (
              <div className="flex flex-col gap-2">
                {recent.map((a) => (
                  <ArtifactRow key={a.artifact_id} artifact={a} compact onOpen={onOpenArtifact} />
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Distilled profile — span 1 */}
        <div className="md:col-span-1">
          <Card
            title="Distilled profile"
            rightAction={
              profile ? (
                <button
                  type="button"
                  className="text-xs font-medium text-databricks-slate hover:text-databricks-navy flex items-center gap-0.5 transition-colors duration-150"
                  onClick={() => onNavigate("profile")}
                  aria-label="Edit profile"
                >
                  Edit profile
                  <ArrowUpRight className="w-3 h-3" aria-hidden="true" />
                </button>
              ) : undefined
            }
          >
            {!profile ? (
              <EmptyState
                icon={User}
                text="No distilled profile yet — accept a proposal to create one."
                ctaLabel="View proposals"
                onCta={() => onNavigate("profile")}
              />
            ) : (
              <dl className="m-0">
                <ProfileField label="Risk tolerance" value={profile.risk_tolerance} />
                <ProfileField
                  label="Goals"
                  value={profile.investment_goals.join(", ")}
                />
                <ProfileField label="Family context" value={profile.family_context} />
                <ProfileField label="Preferences" value={profile.stated_preferences} />
                <ProfileField
                  label="Distilled"
                  value={formatTs(profile.distilled_at)}
                />
              </dl>
            )}
          </Card>
        </div>
      </div>

      {/* Pending proposals */}
      <Card
        title="Pending proposals"
        badge={proposals.length}
        rightAction={
          proposals.length > 3 ? (
            <button
              type="button"
              className="text-xs font-medium text-databricks-slate hover:text-databricks-navy flex items-center gap-0.5 transition-colors duration-150"
              onClick={() => onNavigate("profile")}
              aria-label="See all proposals"
            >
              See all
              <ArrowUpRight className="w-3 h-3" aria-hidden="true" />
            </button>
          ) : undefined
        }
      >
        {!clientId || proposals.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            text={
              clientId
                ? "No pending proposals. Trigger distillation after uploading new artifacts."
                : "Select a client to review proposals."
            }
          />
        ) : (
          <div className="flex flex-col gap-3">
            {pendingProposals.map((p) => (
              <div
                key={p.proposal_id}
                className="flex items-center justify-between gap-4 px-3 py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-muted)]"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-databricks-navy truncate">
                    {p.client_id}
                  </p>
                  <p className="text-xs text-databricks-slate">
                    Proposed {formatTs(p.proposed_at)} · {p.source_artifact_ids.length} source
                    {p.source_artifact_ids.length !== 1 ? "s" : ""}
                  </p>
                </div>
                <button
                  type="button"
                  className="shrink-0 border border-databricks-navy/20 text-databricks-navy hover:bg-[var(--color-databricks-cloud)] text-xs font-medium px-2.5 py-1 rounded-md transition-colors duration-150"
                  onClick={() => onNavigate("profile")}
                  aria-label="Review this proposal"
                >
                  Review
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
