import { type LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  text: string;
  ctaLabel?: string;
  onCta?: () => void;
}

export function EmptyState({ icon: Icon, text, ctaLabel, onCta }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
      <Icon className="w-8 h-8 text-[var(--color-border-strong)]" aria-hidden="true" />
      <p className="text-sm text-databricks-slate max-w-xs">{text}</p>
      {ctaLabel && onCta && (
        <button
          type="button"
          onClick={onCta}
          className="border border-databricks-navy/20 text-databricks-navy hover:bg-[var(--color-databricks-cloud)] text-sm font-medium px-3.5 py-1.5 rounded-md transition-colors duration-150"
          aria-label={ctaLabel}
        >
          {ctaLabel}
        </button>
      )}
    </div>
  );
}
