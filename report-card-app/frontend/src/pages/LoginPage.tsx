import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EyeIcon, EyeOffIcon, SchoolIcon } from "../components/Icons";

const REMEMBERED_EMAIL_KEY = "reportcard_app_remembered_email";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState(() => localStorage.getItem(REMEMBERED_EMAIL_KEY) ?? "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotHint, setShowForgotHint] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/tools" replace />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      localStorage.setItem(REMEMBERED_EMAIL_KEY, email);
      navigate("/tools");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log in");
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
        <form onSubmit={onSubmit} aria-label="Teacher login" className="soft-card p-8" style={{ boxShadow: "var(--shadow-pop)" }}>
          <h1 className="text-[1.65rem] font-extrabold leading-tight" style={{ color: "var(--text-primary)" }}>
            Login
          </h1>
          <p className="text-[1.65rem] font-medium leading-tight" style={{ color: "var(--text-primary)" }}>
            to get started
          </p>

          <div className="mt-6">
            <label htmlFor="login-email" className="sr-only">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="mt-3">
            <label htmlFor="login-password" className="sr-only">
              Password
            </label>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="pr-11"
                required
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

          <div className="mt-3">
            <button
              type="button"
              onClick={() => setShowForgotHint((v) => !v)}
              className="text-sm font-medium transition-colors duration-200 hover:text-[var(--text-primary)]"
              style={{ color: "var(--text-secondary)" }}
            >
              Forgot Password?
            </button>
            {showForgotHint && (
              <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
                Ask your school admin to reset it, or create a new account below.
              </p>
            )}
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
            {busy ? "Logging in…" : "Log in"}
          </button>

          <p className="mt-5 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            New User?{" "}
            <Link to="/signup" className="font-semibold transition-colors duration-200" style={{ color: "var(--text-primary)" }}>
              Register
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
