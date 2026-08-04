import { Fragment, useState } from "react";
import { Sparkles } from "lucide-react";
import { type Proposal, type ClientProfile, type ProposalEdits, formatTs } from "../api";

// ─── Word-diff (LCS) — identical algorithm from original App.tsx ───────────

type DiffToken = { text: string; type: "same" | "removed" | "added" };

function diffWords(oldStr: string, newStr: string): DiffToken[] {
  const a = oldStr.trim().split(/\s+/).filter(Boolean);
  const b = newStr.trim().split(/\s+/).filter(Boolean);
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] =
        a[i] === b[j]
          ? dp[i + 1][j + 1] + 1
          : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const tokens: DiffToken[] = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      tokens.push({ text: a[i], type: "same" });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      tokens.push({ text: a[i], type: "removed" });
      i++;
    } else {
      tokens.push({ text: b[j], type: "added" });
      j++;
    }
  }
  while (i < m) tokens.push({ text: a[i++], type: "removed" });
  while (j < n) tokens.push({ text: b[j++], type: "added" });
  return tokens;
}

type FieldDiff = { label: string; current: string; proposed: string };

function computeDiffs(p: Proposal, cur: ClientProfile | null): FieldDiff[] {
  const norm = (s: string) => (s || "").trim();
  const rows: [string, string, string][] = [
    ["Risk tolerance", cur?.risk_tolerance ?? "", p.risk_tolerance],
    ["Goals", cur?.investment_goals.join(", ") ?? "", p.investment_goals.join(", ")],
    ["Family context", cur?.family_context ?? "", p.family_context],
    ["Preferences", cur?.stated_preferences ?? "", p.stated_preferences],
    ["Summary", cur?.summary ?? "", p.summary],
  ];
  return rows
    .filter(([, current, proposed]) => norm(current) !== norm(proposed))
    .map(([label, current, proposed]) => ({
      label,
      current: current || "—",
      proposed: proposed || "—",
    }));
}

interface ProposalCardProps {
  proposal: Proposal;
  current: ClientProfile | null;
  onAccept: (edits?: ProposalEdits) => void;
  onReject: () => void;
  disabled: boolean;
}

export function ProposalCard({ proposal, current, onAccept, onReject, disabled }: ProposalCardProps) {
  const [editing, setEditing] = useState(false);
  const [risk, setRisk] = useState(proposal.risk_tolerance);
  const [goals, setGoals] = useState(proposal.investment_goals.join(", "));
  const [family, setFamily] = useState(proposal.family_context);
  const [prefs, setPrefs] = useState(proposal.stated_preferences);
  const [summary, setSummary] = useState(proposal.summary);

  const diffs = computeDiffs(proposal, current);

  function acceptEdited() {
    onAccept({
      risk_tolerance: risk,
      investment_goals: goals
        .split(",")
        .map((g) => g.trim())
        .filter(Boolean),
      family_context: family,
      stated_preferences: prefs,
      summary,
    });
  }

  return (
    <div className="rounded-xl border border-[var(--color-border)] border-t-2 border-t-databricks-navy bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface-muted)]">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-databricks-slate shrink-0" aria-hidden="true" />
          <span className="text-xs text-databricks-slate">
            Proposed {formatTs(proposal.proposed_at)}
          </span>
        </div>
        {proposal.source_artifact_ids.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap" aria-label="Source artifacts">
            <span className="text-xs text-databricks-slate">Sources:</span>
            {proposal.source_artifact_ids.map((id) => (
              <span
                key={id}
                className="text-[0.68rem] font-medium px-1.5 py-0.5 rounded-full bg-[var(--color-databricks-cloud)] text-databricks-navy"
              >
                #{id}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Diff / edit body */}
      <div className="px-4 py-3">
        {!editing ? (
          diffs.length === 0 ? (
            <p className="text-sm text-databricks-slate italic">
              No changes from the current profile.
            </p>
          ) : (
            <dl className="m-0 flex flex-col gap-2">
              {diffs.map((d) => (
                <Fragment key={d.label}>
                  <dt className="text-xs font-medium uppercase tracking-wider text-databricks-slate">
                    {d.label}
                  </dt>
                  <dd className="text-sm text-databricks-navy mt-0.5 leading-relaxed">
                    {diffWords(d.current, d.proposed).map((t, idx) => (
                      <span
                        key={idx}
                        className={
                          t.type === "removed"
                            ? "text-databricks-lava line-through"
                            : t.type === "added"
                            ? "text-databricks-moss font-semibold"
                            : ""
                        }
                      >
                        {t.text}{" "}
                      </span>
                    ))}
                  </dd>
                </Fragment>
              ))}
            </dl>
          )
        ) : (
          <div className="flex flex-col gap-3">
            <label className="flex flex-col text-xs text-databricks-slate gap-1">
              Risk tolerance
              <select
                value={risk}
                onChange={(e) => setRisk(e.target.value)}
                className="mt-1 px-2.5 py-1.5 border border-[var(--color-border)] rounded-lg text-sm text-databricks-navy focus:outline-none focus:border-databricks-navy/40"
                aria-label="Proposed risk tolerance"
              >
                <option value="conservative">conservative</option>
                <option value="moderate">moderate</option>
                <option value="aggressive">aggressive</option>
                <option value="unknown">unknown</option>
              </select>
            </label>
            <label className="flex flex-col text-xs text-databricks-slate gap-1">
              Goals (comma-separated)
              <input
                className="mt-1 px-2.5 py-1.5 border border-[var(--color-border)] rounded-lg text-sm text-databricks-navy focus:outline-none focus:border-databricks-navy/40"
                value={goals}
                onChange={(e) => setGoals(e.target.value)}
                aria-label="Proposed investment goals"
              />
            </label>
            <label className="flex flex-col text-xs text-databricks-slate gap-1">
              Family context
              <input
                className="mt-1 px-2.5 py-1.5 border border-[var(--color-border)] rounded-lg text-sm text-databricks-navy focus:outline-none focus:border-databricks-navy/40"
                value={family}
                onChange={(e) => setFamily(e.target.value)}
                aria-label="Proposed family context"
              />
            </label>
            <label className="flex flex-col text-xs text-databricks-slate gap-1">
              Preferences
              <input
                className="mt-1 px-2.5 py-1.5 border border-[var(--color-border)] rounded-lg text-sm text-databricks-navy focus:outline-none focus:border-databricks-navy/40"
                value={prefs}
                onChange={(e) => setPrefs(e.target.value)}
                aria-label="Proposed stated preferences"
              />
            </label>
            <label className="flex flex-col text-xs text-databricks-slate gap-1">
              Summary
              <textarea
                className="mt-1 px-2.5 py-1.5 border border-[var(--color-border)] rounded-lg text-sm text-databricks-navy focus:outline-none focus:border-databricks-navy/40"
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={3}
                aria-label="Proposed profile summary"
              />
            </label>
          </div>
        )}
      </div>

      {/* Action row */}
      <div className="flex gap-2 px-4 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface-muted)]">
        {!editing ? (
          <>
            <button
              type="button"
              className="bg-databricks-red hover:bg-[#e02f1c] text-white font-medium text-sm px-3.5 py-1.5 rounded-md shadow-sm transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => onAccept()}
              disabled={disabled}
              aria-label="Accept proposal"
            >
              Accept
            </button>
            <button
              type="button"
              className="border border-databricks-navy/20 text-databricks-navy hover:bg-[var(--color-databricks-cloud)] text-sm font-medium px-3.5 py-1.5 rounded-md transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => setEditing(true)}
              disabled={disabled}
              aria-label="Edit proposal before accepting"
            >
              Edit
            </button>
            <button
              type="button"
              className="text-databricks-lava hover:bg-red-50 text-sm font-medium px-3.5 py-1.5 rounded-md transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={onReject}
              disabled={disabled}
              aria-label="Reject proposal"
            >
              Reject
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="bg-databricks-red hover:bg-[#e02f1c] text-white font-medium text-sm px-3.5 py-1.5 rounded-md shadow-sm transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={acceptEdited}
              disabled={disabled}
              aria-label="Save edits and accept proposal"
            >
              Save &amp; Accept
            </button>
            <button
              type="button"
              className="border border-databricks-navy/20 text-databricks-navy hover:bg-[var(--color-databricks-cloud)] text-sm font-medium px-3.5 py-1.5 rounded-md transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={() => setEditing(false)}
              disabled={disabled}
              aria-label="Discard edits"
            >
              Discard edits
            </button>
          </>
        )}
      </div>
    </div>
  );
}
