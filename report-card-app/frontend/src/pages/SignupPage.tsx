import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { EyeIcon, EyeOffIcon } from "../components/Icons";

export function SignupPage() {
  const { user, signup } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signup(email, password, displayName);
      navigate("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create account");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10" style={{ background: "var(--page-plane)" }}>
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="icon-chip" style={{ width: "3rem", height: "3rem", fontWeight: 700 }}>
            RC
          </span>
          <div className="font-display mt-3 text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            Report Card Generator
          </div>
        </div>
        <form onSubmit={onSubmit} aria-label="Create account" className="soft-card p-8" style={{ boxShadow: "var(--shadow-pop)" }}>
          <h1 className="text-[1.65rem] font-extrabold leading-tight" style={{ color: "var(--text-primary)" }}>
            Register
          </h1>
          <p className="text-[1.65rem] font-medium leading-tight" style={{ color: "var(--text-primary)" }}>
            to get started
          </p>

          <div className="mt-6">
            <label htmlFor="signup-name" className="sr-only">
              Your name
            </label>
            <input
              id="signup-name"
              type="text"
              autoComplete="name"
              placeholder="Your name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
            />
          </div>

          <div className="mt-3">
            <label htmlFor="signup-email" className="sr-only">
              Email
            </label>
            <input
              id="signup-email"
              type="email"
              autoComplete="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="mt-3">
            <label htmlFor="signup-password" className="sr-only">
              Password
            </label>
            <div className="relative">
              <input
                id="signup-password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
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

          {error && (
            <p role="alert" className="mt-3 rounded-lg p-2.5 text-sm" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="accent-fill mt-5 w-full rounded-xl px-4 py-3 text-sm font-semibold text-white shadow-sm transition-all duration-200 active:scale-[0.99] disabled:opacity-60"
          >
            {busy ? "Creating…" : "Create account"}
          </button>

          <p className="mt-5 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
            Already have an account?{" "}
            <Link to="/login" className="font-semibold transition-colors duration-200" style={{ color: "var(--text-primary)" }}>
              Log in
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
