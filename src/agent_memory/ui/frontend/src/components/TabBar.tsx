export type TabId = "overview" | "timeline" | "brainstorm" | "profile";

interface Tab {
  id: TabId;
  label: string;
  badge?: number;
}

interface TabBarProps {
  active: TabId;
  onChange: (id: TabId) => void;
  pendingCount: number;
}

export function TabBar({ active, onChange, pendingCount }: TabBarProps) {
  const tabs: Tab[] = [
    { id: "overview", label: "Overview" },
    { id: "timeline", label: "Timeline" },
    { id: "brainstorm", label: "Brainstorm" },
    { id: "profile", label: "Profile & Proposals", badge: pendingCount || undefined },
  ];

  return (
    <div
      className="sticky top-[calc(3rem+3.75rem)] z-30 bg-white border-b border-[var(--color-border)] px-6"
      role="tablist"
      aria-label="Main navigation tabs"
    >
      <div className="max-w-screen-xl mx-auto flex gap-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active === tab.id}
            aria-controls={`tabpanel-${tab.id}`}
            className={[
              "relative flex items-center gap-1.5 px-4 py-3 text-sm font-medium transition-colors duration-150 border-b-2 -mb-px focus:outline-none",
              active === tab.id
                ? "border-databricks-red text-databricks-navy"
                : "border-transparent text-databricks-slate hover:text-databricks-navy hover:border-[var(--color-border-strong)]",
            ].join(" ")}
            onClick={() => onChange(tab.id)}
          >
            {tab.label}
            {tab.badge != null && tab.badge > 0 && (
              <span
                className="inline-flex items-center justify-center min-w-[1.1rem] h-[1.1rem] px-1 rounded-full bg-databricks-red text-white text-[0.6rem] font-bold leading-none"
                aria-label={`${tab.badge} pending`}
              >
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
