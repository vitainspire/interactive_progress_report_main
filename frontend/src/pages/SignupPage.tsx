import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Logo } from "../components/Logo";
import { ThemeToggleButton } from "../components/ThemeToggleButton";

export function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [schoolName, setSchoolName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signup(email, password, displayName, schoolName);
      // A brand-new account has no classes yet — "/" (HomeRedirect) sends
      // them to /manage-classes to create their first one.
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-4" style={{ background: "var(--page-plane)" }}>
      <ThemeToggleButton className="absolute right-4 top-4" />
      <div className="w-full max-w-sm">
        <div className="mb-7 text-center">
          <div className="mx-auto mb-3 flex w-fit items-center justify-center">
            <Logo size={44} />
          </div>
          <div className="font-display text-xl font-bold" style={{ color: "var(--text-primary)" }}>
            Create your account
          </div>
          <div className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Your own students, your own data — private to you
          </div>
        </div>

        <form onSubmit={handleSubmit} className="soft-card p-6">
          <label className="block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Your name</span>
            <input
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
          <label className="mt-3 block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>School name (optional)</span>
            <input
              value={schoolName}
              onChange={(e) => setSchoolName(e.target.value)}
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
          <label className="mt-3 block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
          <label className="mt-3 block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Password (min 8 characters)</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>

          {error && (
            <p className="mt-3 rounded-xl p-2.5 text-xs" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="gradient-fill mt-5 w-full rounded-full px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-50"
          >
            Create account
          </button>
        </form>

        <p className="mt-6 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
          Already have an account?{" "}
          <Link to="/login" className="font-semibold" style={{ color: "var(--accent)" }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
