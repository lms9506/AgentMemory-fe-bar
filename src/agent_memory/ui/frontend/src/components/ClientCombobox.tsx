import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search, Users } from "lucide-react";
import { type ClientInfo } from "../api";

interface ClientComboboxProps {
  clients: ClientInfo[];
  clientId: string;
  onSelect: (id: string) => void;
  /** When true, render as a compact "Switch client" chip (banner already shows identity). */
  compact?: boolean;
}

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export function ClientCombobox({ clients, clientId, onSelect, compact = false }: ClientComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const current = clients.find((c) => c.id === clientId);

  const filtered = query
    ? clients.filter(
        (c) =>
          c.display_name.toLowerCase().includes(query.toLowerCase()) ||
          c.id.toLowerCase().includes(query.toLowerCase()),
      )
    : clients;

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
    }
  }, [open]);

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      {compact ? (
        <button
          type="button"
          className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[var(--color-border)] rounded-md text-sm font-medium text-databricks-navy hover:border-databricks-navy/40 hover:bg-[var(--color-surface-muted)] transition-colors duration-150 shadow-sm"
          aria-label="Switch client"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          disabled={clients.length === 0}
        >
          <Users className="w-4 h-4 text-databricks-slate" aria-hidden="true" />
          Switch client
          <ChevronDown className="w-3.5 h-3.5 text-databricks-slate" aria-hidden="true" />
        </button>
      ) : (
        <button
          type="button"
          className="flex items-center gap-2.5 px-3 py-1.5 bg-white border border-[var(--color-border)] rounded-lg text-sm font-medium text-databricks-navy hover:border-databricks-navy/40 hover:bg-[var(--color-surface-muted)] transition-colors duration-150 min-w-48 shadow-sm"
          aria-label="Select client"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          disabled={clients.length === 0}
        >
          {clients.length === 0 ? (
            <span className="text-databricks-slate">Loading clients…</span>
          ) : current ? (
            <>
              <span
                className="w-6 h-6 rounded-full bg-gradient-to-br from-databricks-navy to-databricks-red flex items-center justify-center text-[0.6rem] font-bold text-white shrink-0"
                aria-hidden="true"
              >
                {initials(current.display_name)}
              </span>
              <span className="flex-1 text-left truncate">{current.display_name}</span>
            </>
          ) : (
            <span className="text-databricks-slate">Select client…</span>
          )}
          <ChevronDown className="w-3.5 h-3.5 text-databricks-slate shrink-0" aria-hidden="true" />
        </button>
      )}

      {open && (
        <div
          className="absolute left-0 top-full mt-1 w-72 bg-white rounded-xl border border-[var(--color-border)] shadow-xl z-50 overflow-hidden"
          role="listbox"
          aria-label="Client list"
        >
          {/* Search */}
          <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--color-border)]">
            <Search className="w-3.5 h-3.5 text-databricks-slate shrink-0" aria-hidden="true" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 text-sm outline-none text-databricks-navy placeholder:text-databricks-slate"
              placeholder="Search clients…"
              aria-label="Search clients"
            />
          </div>

          {/* List */}
          <ul className="max-h-64 overflow-y-auto py-1" role="presentation">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-databricks-slate">No clients found</li>
            ) : (
              filtered.map((c) => (
                <li key={c.id} role="none">
                  <button
                    type="button"
                    role="option"
                    aria-selected={c.id === clientId}
                    className={[
                      "w-full text-left flex items-center gap-2.5 px-3 py-2 text-sm transition-colors duration-150",
                      c.id === clientId
                        ? "bg-[var(--color-databricks-cloud)] text-databricks-navy font-medium"
                        : "text-databricks-navy hover:bg-[var(--color-surface-muted)]",
                    ].join(" ")}
                    onClick={() => {
                      onSelect(c.id);
                      setOpen(false);
                    }}
                  >
                    <span
                      className="w-6 h-6 rounded-full bg-gradient-to-br from-databricks-navy to-databricks-red flex items-center justify-center text-[0.6rem] font-bold text-white shrink-0"
                      aria-hidden="true"
                    >
                      {initials(c.display_name)}
                    </span>
                    <div className="flex flex-col min-w-0">
                      <span className="truncate font-medium">{c.display_name}</span>
                      <span className="text-xs text-databricks-slate truncate">{c.id}</span>
                    </div>
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
