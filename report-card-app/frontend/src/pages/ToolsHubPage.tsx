import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { BarChartIcon, CalendarIcon, SheetIcon } from "../components/Icons";

const ACCENTS = {
  navy: { fg: "var(--accent)", soft: "var(--accent-soft)" },
  green: { fg: "var(--status-good)", soft: "var(--status-good-soft)" },
  muted: { fg: "var(--text-muted)", soft: "var(--border)" },
} as const;

function ToolCard({
  to,
  icon,
  title,
  body,
  badge,
  accent,
}: {
  to?: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  badge?: string;
  accent: keyof typeof ACCENTS;
}) {
  const { fg, soft } = ACCENTS[accent];

  const inner = (
    <>
      <div
        className="flex h-11 w-11 items-center justify-center rounded-xl"
        style={{ background: soft, color: fg }}
      >
        {icon}
      </div>
      {badge && (
        <span className="pill absolute right-5 top-5">{badge}</span>
      )}
      <h2 className="font-display mt-4 text-lg font-bold" style={{ color: "var(--text-primary)" }}>
        {title}
      </h2>
      <p className="mt-1.5 flex-1 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        {body}
      </p>
      {to && (
        <span
          className="accent-fill mt-5 inline-flex w-fit items-center rounded-md px-4 py-2 text-sm font-semibold text-white"
        >
          Open
        </span>
      )}
    </>
  );

  const sharedStyle = { borderTop: `3px solid ${to ? fg : "var(--border)"}` };

  if (!to) {
    return (
      <div className="soft-card relative flex flex-col p-5" style={{ ...sharedStyle, opacity: 0.65 }}>
        {inner}
      </div>
    );
  }

  return (
    <Link
      to={to}
      className="soft-card reveal group relative flex flex-col p-5 transition-transform duration-200 hover:-translate-y-0.5"
      style={sharedStyle}
    >
      {inner}
    </Link>
  );
}

export function ToolsHubPage() {
  const { user } = useAuth();
  const schoolName = user?.default_school_name || "Your school";

  return (
    <section>
      <header
        className="dot-grid-plane-dark relative overflow-hidden rounded-2xl px-6 py-7 sm:px-8 sm:py-9"
        style={{ background: "var(--accent-strong)" }}
      >
        <p className="font-serif text-2xl font-medium leading-tight text-white sm:text-3xl">{schoolName}</p>
        <p className="mt-2 max-w-md text-sm" style={{ color: "rgba(255,255,255,0.75)" }}>
          Everything your school runs on, kept in one place. Pick a tool below to get started.
        </p>
      </header>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ToolCard
          to="/dashboard"
          icon={<SheetIcon size={20} />}
          title="Report Card Generator"
          body="Upload your class's marks sheet and generate bilingual report cards, a class performance overview, and parent-ready WhatsApp links."
          accent="navy"
        />
        <ToolCard
          to="/timetable"
          icon={<CalendarIcon size={20} />}
          title="Dynamic Timetable"
          body="Build your school's weekly timetable across every class and teacher, and instantly find a substitute when someone's absent."
          accent="green"
        />
        <ToolCard
          icon={<BarChartIcon size={20} />}
          title="Student Grade Promoter"
          badge="Coming soon"
          body="Promote students to their next grade at year-end based on their results, in one step across every class."
          accent="muted"
        />
      </div>
    </section>
  );
}
