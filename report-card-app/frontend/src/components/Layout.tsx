import { useEffect, useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { DocumentIcon, LogoutIcon, PlugIcon, SchoolIcon } from "./Icons";
import type { ReferenceDocument } from "../types";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [pendingDocCount, setPendingDocCount] = useState(0);

  function refreshPendingDocCount() {
    Promise.all([
      api.get<ReferenceDocument[]>("/reference-documents?status=pending"),
      api.get<ReferenceDocument[]>("/reference-documents?status=failed"),
    ])
      .then(([pending, failed]) => setPendingDocCount(pending.length + failed.length))
      .catch(() => {});
  }

  useEffect(() => {
    if (user) refreshPendingDocCount();
  }, [user]);

  return (
    <div className="min-h-screen">
      <header style={{ background: "var(--surface-1)", borderBottom: "1px solid var(--border)" }}>
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-3.5">
          <Link to="/tools" className="flex items-center gap-3">
            <div className="icon-chip">
              <SchoolIcon size={18} />
            </div>
            <div className="font-display text-lg font-bold" style={{ color: "var(--text-primary)" }}>
              School Admin Tools
            </div>
          </Link>
          {user && (
            <details className="group relative" onToggle={(e) => (e.currentTarget as HTMLDetailsElement).open && refreshPendingDocCount()}>
              <summary
                className="flex cursor-pointer list-none items-center gap-2 rounded-full border py-1 pl-1 pr-3 transition-colors duration-200 hover:bg-[var(--accent-soft)]"
                style={{ borderColor: "var(--border)" }}
              >
                <span
                  className="flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold text-white"
                  style={{ background: "var(--text-primary)" }}
                >
                  {initials(user.display_name)}
                </span>
                <span className="hidden text-sm font-medium sm:inline" style={{ color: "var(--text-primary)" }}>
                  {user.display_name}
                </span>
              </summary>
              <div
                className="soft-card absolute right-0 z-20 mt-2 w-56 overflow-hidden p-1.5"
                style={{ boxShadow: "var(--shadow-pop)" }}
              >
                <div className="px-2.5 py-2">
                  <div className="truncate text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    {user.display_name}
                  </div>
                  <div className="truncate text-xs" style={{ color: "var(--text-muted)" }}>
                    {user.email}
                  </div>
                </div>
                <div className="my-1 h-px" style={{ background: "var(--border)" }} />
                <Link
                  to="/school-profile"
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)]"
                  style={{ color: "var(--text-primary)" }}
                >
                  <SchoolIcon size={15} />
                  School profile
                </Link>
                <Link
                  to="/integrations"
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)]"
                  style={{ color: "var(--text-primary)" }}
                >
                  <PlugIcon size={15} />
                  WhatsApp / SMS setup
                </Link>
                <Link
                  to="/reference-documents"
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)]"
                  style={{ color: "var(--text-primary)" }}
                >
                  <DocumentIcon size={15} />
                  Syllabus/blueprint review{pendingDocCount > 0 ? ` (${pendingDocCount})` : ""}
                </Link>
                <button
                  onClick={() => {
                    logout();
                    navigate("/login");
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-mark-soft)]"
                  style={{ color: "var(--accent-mark)" }}
                >
                  <LogoutIcon size={15} />
                  Log out
                </button>
              </div>
            </details>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-7">
        <Outlet />
      </main>
    </div>
  );
}
