import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { SchoolIcon } from "../components/Icons";

export function ForgotPasswordPage() {
  const { requestPasswordReset } = useAuth();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await requestPasswordReset(email.trim());
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the reset email");
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
            Reset your password
          </h1>

          {sent ? (
            <p className="mt-4 text-sm" style={{ color: "var(--text-secondary)" }}>
              If an account exists for <b>{email.trim()}</b>, a reset link has been sent — check your inbox (and spam
              folder). The link works once and expires in 60 minutes.
            </p>
          ) : (
            <form onSubmit={onSubmit}>
              <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                Enter the email you signed up with and we'll send you a link to set a new password.
              </p>
              <div className="mt-5">
                <label htmlFor="forgot-email" className="sr-only">
                  Email
                </label>
                <input
                  id="forgot-email"
                  type="email"
                  autoComplete="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
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
                {busy ? "Sending…" : "Send reset link"}
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
