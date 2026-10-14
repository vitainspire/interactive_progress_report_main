import { Link, useLocation } from "react-router-dom";
import { ChalkboardIcon, GraduationCapIcon, ShieldIcon } from "./Icons";

const ROLES = [
  { to: "/login", label: "Admin / Principal", icon: ShieldIcon },
  { to: "/login", label: "Teacher", icon: ChalkboardIcon },
  { to: "/student-login", label: "Student / Parent", icon: GraduationCapIcon },
] as const;

/** Small icon-only switcher on the login screens — lets someone pick which
 * kind of login they want without reading a line of text. Admin and
 * teacher land on the same /login form (the account itself decides the
 * role), only the student/parent icon goes to the separate roll-number
 * login. */
export function RoleSwitcher() {
  const location = useLocation();
  return (
    <div className="mt-4 flex items-center justify-center gap-2">
      {ROLES.map(({ to, label, icon: Icon }) => {
        const active = location.pathname === to;
        return (
          <Link
            key={label}
            to={to}
            title={label}
            aria-label={label}
            className="flex h-10 w-10 items-center justify-center rounded-full border shadow-sm transition-colors hover:bg-[var(--accent-soft)]"
            style={{
              borderColor: active ? "var(--accent)" : "var(--border)",
              color: active ? "var(--accent)" : "var(--text-secondary)",
              background: active ? "var(--accent-soft)" : "var(--surface-1)",
            }}
          >
            <Icon size={18} />
          </Link>
        );
      })}
    </div>
  );
}
