import type { ReactNode } from "react";

type Accent = "default" | "gold" | "mark";

const ACCENT_COLOR: Record<Accent, string> = {
  default: "var(--accent)",
  gold: "var(--accent-gold)",
  mark: "var(--accent-mark)",
};

const ACCENT_SOFT: Record<Accent, string> = {
  default: "var(--accent-soft)",
  gold: "var(--accent-gold-soft)",
  mark: "var(--accent-mark-soft)",
};

export function StatTile({
  label,
  value,
  sub,
  accent = "default",
  index = 0,
  icon,
  visual,
  onClick,
}: {
  label: string;
  value?: string | number;
  sub?: string;
  accent?: Accent;
  index?: number;
  icon?: ReactNode;
  /** A custom visual (e.g. a gauge) rendered instead of the plain mono value. */
  visual?: ReactNode;
  /** Makes the tile a drill-down button instead of a static card. */
  onClick?: () => void;
}) {
  const color = ACCENT_COLOR[accent];
  const body = (
    <>
      <div className="flex items-center gap-2">
        {icon && (
          <span className="icon-chip" style={{ background: ACCENT_SOFT[accent], color }}>
            {icon}
          </span>
        )}
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em]" style={{ color: "var(--text-secondary)" }}>
          {label}
        </span>
      </div>
      {visual ? (
        <div className="mt-3">{visual}</div>
      ) : (
        <div className="font-mono mt-3 text-[1.8rem] font-bold leading-none" style={{ color: "var(--text-primary)" }}>
          {value}
        </div>
      )}
      {sub && (
        <div className="mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
          {sub}
        </div>
      )}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="soft-card reveal block w-full p-5 text-left transition-transform duration-150 hover:-translate-y-0.5 hover:shadow-md"
        style={{ animationDelay: `${index * 70}ms` }}
      >
        {body}
      </button>
    );
  }

  return (
    <div className="soft-card reveal p-5" style={{ animationDelay: `${index * 70}ms` }}>
      {body}
    </div>
  );
}
