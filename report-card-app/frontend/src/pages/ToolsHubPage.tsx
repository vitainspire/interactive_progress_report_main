import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { CalendarIcon, SheetIcon } from "../components/Icons";

function ToolCard({
  to,
  icon,
  title,
  body,
  badge,
}: {
  to: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  badge?: string;
}) {
  return (
    <Link
      to={to}
      className="soft-card reveal group relative flex flex-col p-6 transition-all duration-200 hover:shadow-lg"
    >
      <div className="flex items-start justify-between gap-3">
        <span className="icon-chip" style={{ width: "2.6rem", height: "2.6rem" }}>
          {icon}
        </span>
        {badge && <span className="pill">{badge}</span>}
      </div>
      <h2 className="font-display mt-4 text-lg font-bold" style={{ color: "var(--text-primary)" }}>
        {title}
      </h2>
      <p className="mt-1.5 text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        {body}
      </p>
      <span
        className="mt-4 text-sm font-semibold transition-colors duration-200"
        style={{ color: "var(--accent)" }}
      >
        Open →
      </span>
    </Link>
  );
}

export function ToolsHubPage() {
  const { user } = useAuth();

  return (
    <section>
      <header>
        <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          {user?.default_school_name ? `${user.default_school_name} — Tools` : "Your tools"}
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Everything your school uses, in one account. Pick a tool to get started.
        </p>
      </header>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ToolCard
          to="/dashboard"
          icon={<SheetIcon size={20} />}
          title="Report Card Generator"
          body="Upload your class's marks sheet and generate bilingual report cards, a class performance overview, and parent-ready WhatsApp links."
        />
        <ToolCard
          to="/timetable"
          icon={<CalendarIcon size={20} />}
          title="Dynamic Timetable"
          body="Build your school's weekly timetable across every class and teacher, and instantly find a substitute when someone's absent."
        />
      </div>
    </section>
  );
}
