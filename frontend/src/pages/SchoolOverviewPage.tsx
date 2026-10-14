import { Link } from "react-router-dom";
import { useClasses } from "../context/ClassesContext";
import { BookIcon, LayersIcon, PeopleIcon } from "../components/Icons";

/** The admin's landing page: every class at a glance, in the same card
 * style the rest of the app uses — click a card to open that class's own
 * Dashboard (the per-class "Class Overview" page). */
export function SchoolOverviewPage() {
  const { classes, loading } = useClasses();

  if (loading) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  return (
    <div>
      <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
        School Overview
      </h1>
      <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
        Every class you're tracking — open one to see its dashboard.
      </p>

      {classes.length === 0 ? (
        <div className="soft-card reveal mt-5 p-6 text-center">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            No classes yet.
          </p>
          <Link to="/manage-classes" className="mt-2 inline-block text-sm font-medium" style={{ color: "var(--accent)" }}>
            Create your first class →
          </Link>
        </div>
      ) : (
        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {classes.map((c, i) => (
            <Link
              key={c.id}
              to={`/c/${c.id}`}
              className="soft-card reveal block p-5 transition-shadow hover:shadow-lg"
              style={{ animationDelay: `${i * 70}ms` }}
            >
              <div className="icon-chip">
                <BookIcon size={16} />
              </div>
              <div className="font-display mt-3 text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                {c.name}
              </div>
              <div className="mt-3 flex items-center gap-4 text-sm" style={{ color: "var(--text-secondary)" }}>
                <span className="inline-flex items-center gap-1.5">
                  <PeopleIcon size={16} /> {c.total_students} students
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <LayersIcon size={16} /> {c.sections.length} section{c.sections.length === 1 ? "" : "s"}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
