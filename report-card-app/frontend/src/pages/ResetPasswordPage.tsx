import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EyeIcon, EyeOffIcon, SchoolIcon } from "../components/Icons";

export function ResetPasswordPage() {
  const { resetPassword } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset your password");
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
        <div className="soft-card p-8" style={{ boxShadow: "var(--shadow-pop)" }}>
          <h1 className="text-[1.65rem] font-extrabold leading-tight" style={{ color: "var(--text-primary)" }}>
            Set a new password
          </h1>

          {!token ? (
            <p className="mt-4 text-sm" style={{ color: "var(--text-secondary)" }}>
              This link is missing its reset code.{" "}
              <Link to="/forgot-password" className="font-semibold" style={{ color: "var(--accent)" }}>
                Request a new one
              </Link>
              .
            </p>
          ) : done ? (
            <>
              <p className="mt-4 text-sm" style={{ color: "var(--text-secondary)" }}>
                Your password has been reset.
              </p>
              <button
                type="button"
                onClick={() => navigate("/login")}
                className="accent-fill mt-5 w-full rounded-md px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 active:scale-[0.99]"
              >
                Go to login
              </button>
            </>
          ) : (
            <form onSubmit={onSubmit}>
              <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                Choose a new password (at least 8 characters).
              </p>
              <div className="mt-5">
                <label htmlFor="reset-password" className="sr-only">
                  New password
                </label>
                <div className="relative">
                  <input
                    id="reset-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="New password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pr-11"
                    required
                    minLength={8}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                    className="absolute inset-y-0 right-0 flex w-10 items-center justify-center transition-colors duration-200 hover:text-[var(--text-primary)]"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {showPassword ? <EyeOffIcon size={17} /> : <EyeIcon size={17} />}
                  </button>
                </div>
              </div>

              {error && (
                <p role="alert" className="mt-3 rounded-lg p-2.5 text-sm" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={busy}
                className="accent-fill mt-5 w-full rounded-md px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 active:scale-[0.99] disabled:opacity-60"
              >
                {busy ? "Saving…" : "Set new password"}
              </button>
            </form>
          )}

          <p className="mt-5 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            <Link to="/login" className="font-semibold transition-colors duration-200" style={{ color: "var(--text-primary)" }}>
              Back to login
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
