import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useClasses } from "../context/ClassesContext";
import type { Role } from "../types";
import { Logo } from "./Logo";
import { ThemeToggleButton } from "./ThemeToggleButton";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

/** Nav links for admin/teacher depend on which class is currently open
 * (from the URL). "Dashboard" always resolves sensibly — to the School
 * Overview (admin) or the class picker (teacher) when no class is in
 * view, or to that class's own dashboard once one is open. Links that
 * only make sense INSIDE a class (Uploads, Students) are left out
 * entirely rather than falling back to "/" too, which would just
 * duplicate "Dashboard" and show both as active at once. */
function buildNavItems(role: Role, classId: string | undefined): NavItem[] {
  const base = classId ? `/c/${classId}` : "/";
  if (role === "admin") {
    const items: NavItem[] = [
      { to: base, label: "Dashboard", end: true },
      { to: "/manage-classes", label: "Classes" },
    ];
    if (classId) items.push({ to: `${base}/uploads`, label: "Uploads" });
    items.push({ to: "/accounts", label: "Accounts" }, { to: "/settings", label: "Settings" });
    return items;
  }
  if (role === "teacher") {
    const items: NavItem[] = [{ to: base, label: "Dashboard", end: true }];
    if (classId) items.push({ to: `${base}/sections`, label: "Students" });
    return items;
  }
  // A student's only page is their own report card, reached directly off
  // "/" (see HomeRedirect in App.tsx) — no nav links needed.
  return [];
}

function ClassSwitcher({ classId }: { classId: string | undefined }) {
  const { classes } = useClasses();
  const navigate = useNavigate();
  if (classes.length < 2) return null;
  return (
    <select
      value={classId ?? ""}
      onChange={(e) => e.target.value && navigate(`/c/${e.target.value}`)}
      className="rounded-full border px-3 py-1.5 text-xs font-medium"
      style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
      aria-label="Switch class"
    >
      {!classId && <option value="">Choose a class…</option>}
      {classes.map((c) => (
        <option key={c.id} value={c.id}>
          {c.name}
        </option>
      ))}
    </select>
  );
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { classId } = useParams();
  const navItems = user ? buildNavItems(user.role, classId) : [];

  return (
    <div className="min-h-screen">
      <ThemeToggleButton className="fixed right-4 top-4 z-50 shadow-sm" />
      <header style={{ background: "var(--surface-1)", borderBottom: "1px solid var(--border)" }}>
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-3.5">
          <Link to="/" className="flex items-center gap-3">
            <Logo size={36} />
            <div>
              <div className="font-display text-lg font-bold leading-tight" style={{ color: "var(--text-primary)" }}>
                Interactive Progress Report
              </div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }} lang="te">
                విద్యార్థుల పురోగతి నివేదిక — Student Progress Register
              </div>
            </div>
          </Link>
          <nav className="flex flex-wrap items-center gap-1">
            {(user?.role === "admin" || user?.role === "teacher") && <ClassSwitcher classId={classId} />}
            {navItems.map((item) => (
              <NavLink
                key={item.label}
                to={item.to}
                end={item.end}
                className="rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors"
                style={({ isActive }) => ({
                  color: isActive ? "var(--accent)" : "var(--text-secondary)",
                  background: isActive ? "var(--accent-soft)" : "transparent",
                })}
              >
                {item.label}
              </NavLink>
            ))}
            <div className="ml-2 flex items-center gap-3 border-l pl-3" style={{ borderColor: "var(--border)" }}>
              <span className="hidden text-xs sm:inline" style={{ color: "var(--text-muted)" }}>
                {user?.display_name}
                {user?.school_name ? ` · ${user.school_name}` : ""}
              </span>
              <button
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--accent-soft)]"
                style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
              >
                Log out
              </button>
            </div>
          </nav>
        </div>
        <div className="accent-rule" />
        {user?.is_demo && (
          <div
            className="px-4 py-1.5 text-center text-xs font-medium"
            style={{ color: "var(--text-muted)" }}
          >
            You're viewing the demo data —{" "}
            <NavLink to="/signup" className="underline" style={{ color: "var(--text-muted)" }} onClick={logout}>
              sign up
            </NavLink>{" "}
            to upload your own school's data.
          </div>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-7">
        <Outlet />
      </main>
    </div>
  );
}
