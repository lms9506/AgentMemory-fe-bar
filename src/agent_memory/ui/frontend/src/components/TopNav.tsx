import { useState } from "react";
import { ChevronDown } from "lucide-react";

interface TopNavProps {
  advisorId: string;
  advisors: string[];
  onAdvisorChange: (id: string) => void;
}

function humanizeAdvisor(id: string): string {
  // e.g. "advisor_demo_01" -> "Demo Advisor"; "advisor_alex_kim" -> "Alex Kim".
  const parts = id
    .replace(/^advisor[_-]?/i, "")
    .split(/[_\s-]+/)
    .filter((p) => p && !/^\d+$/.test(p));
  if (parts.length === 0) return id;
  const titled = parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase());
  // If the id started with "advisor_", append the role for demo IDs.
  if (/^advisor/i.test(id) && parts.length === 1) {
    return `${titled[0]} Advisor`;
  }
  return titled.join(" ");
}

function initials(id: string): string {
  return humanizeAdvisor(id)
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export function TopNav({ advisorId, advisors, onAdvisorChange }: TopNavProps) {
  const [open, setOpen] = useState(false);

  return (
    <nav
      className="sticky top-0 z-50 bg-databricks-navy text-white flex items-center justify-between px-6 h-12 shadow-sm"
      aria-label="Top navigation"
    >
      {/* Wordmark */}
      <div className="flex items-center gap-2.5 select-none">
        <span
          className="w-2.5 h-2.5 rounded-full bg-databricks-red"
          aria-hidden="true"
        />
        <span className="text-base font-semibold tracking-tight leading-none">
          Smart Advise
        </span>
      </div>

      {/* Advisor chip */}
      <div className="relative">
        <button
          type="button"
          className="flex items-center gap-2 px-2.5 py-1 rounded-md hover:bg-white/10 transition-colors duration-150 text-sm font-medium"
          aria-label="Advisor selector"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {/* Avatar pill */}
          <span
            className="w-6 h-6 rounded-full bg-gradient-to-br from-databricks-navy to-databricks-red flex items-center justify-center text-[0.6rem] font-bold border border-white/20"
            aria-hidden="true"
          >
            {initials(advisorId)}
          </span>
          <span className="hidden sm:inline max-w-40 truncate">{humanizeAdvisor(advisorId)}</span>
          <ChevronDown className="w-3.5 h-3.5 opacity-70" aria-hidden="true" />
        </button>

        {open && (
          <div
            className="absolute right-0 top-full mt-1 w-56 bg-white rounded-xl border border-[var(--color-border)] shadow-lg z-50 py-1 overflow-hidden"
            role="listbox"
            aria-label="Advisor list"
          >
            {advisors.length === 0 ? (
              <div className="px-3 py-2 text-sm text-databricks-slate">
                <select
                  value={advisorId}
                  onChange={(e) => {
                    onAdvisorChange(e.target.value);
                    setOpen(false);
                  }}
                  className="w-full text-sm border border-[var(--color-border)] rounded px-2 py-1"
                  aria-label="Select advisor"
                >
                  <option value={advisorId}>{advisorId}</option>
                </select>
              </div>
            ) : (
              advisors.map((a) => (
                <button
                  key={a}
                  type="button"
                  role="option"
                  aria-selected={a === advisorId}
                  className={[
                    "w-full text-left flex items-center gap-2 px-3 py-2 text-sm transition-colors duration-150",
                    a === advisorId
                      ? "bg-[var(--color-databricks-cloud)] text-databricks-navy font-medium"
                      : "text-databricks-navy hover:bg-[var(--color-surface-muted)]",
                  ].join(" ")}
                  onClick={() => {
                    onAdvisorChange(a);
                    setOpen(false);
                  }}
                >
                  <span
                    className="w-5 h-5 rounded-full bg-gradient-to-br from-databricks-navy to-databricks-red flex items-center justify-center text-[0.55rem] font-bold text-white shrink-0"
                    aria-hidden="true"
                  >
                    {initials(a)}
                  </span>
                  <div className="flex flex-col min-w-0">
                    <span className="truncate font-medium">{humanizeAdvisor(a)}</span>
                    <span className="text-xs text-databricks-slate truncate">{a}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
