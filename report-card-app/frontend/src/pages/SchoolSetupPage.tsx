import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { SchoolIcon } from "../components/Icons";

/** A mandatory one-time gate for any account that reached the app without
 * a school name already on file — a fresh signup already collects this
 * (see SignupPage), so in practice this only matters for an account that
 * predates that field. App.tsx routes here instead of past this page
 * whenever `user.default_school_name` is blank. */
export function SchoolSetupPage() {
  const { user, setSchoolName } = useAuth();
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!user) return <Navigate to="/login" replace />;
  if (user.default_school_name) return <Navigate to="/tools" replace />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await setSchoolName(value);
      navigate("/tools");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your school name");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10" style={{ background: "var(--page-plane)" }}>
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="icon-chip" style={{ width: "3rem", height: "3rem" }}>
            <SchoolIcon size={26} />
          </span>
          <div className="font-display mt-3 text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            School Admin Tools
          </div>
        </div>
        <form onSubmit={onSubmit} aria-label="Set up your school" className="soft-card p-8" style={{ boxShadow: "var(--shadow-pop)" }}>
          <h1 className="text-[1.65rem] font-extrabold leading-tight" style={{ color: "var(--text-primary)" }}>
            Set up your school
          </h1>
          <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
            This name is printed on every report card and timetable you generate — one-time setup before you get
            started.
          </p>

          <div className="mt-6">
            <label htmlFor="school-setup-name" className="sr-only">
              School name
            </label>
            <input
              id="school-setup-name"
              type="text"
              autoComplete="organization"
              placeholder="e.g. S.P.P High School, Gurajanapalli"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
              autoFocus
            />
          </div>

          {error && (
            <p role="alert" className="mt-3 rounded-lg p-2.5 text-sm" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !value.trim()}
            className="accent-fill mt-5 w-full rounded-md px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 active:scale-[0.99] disabled:opacity-60"
          >
            {busy ? "Saving…" : "Continue"}
          </button>
        </form>
      </div>
    </main>
  );
}
