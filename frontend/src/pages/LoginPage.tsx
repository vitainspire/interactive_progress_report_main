import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Logo } from "../components/Logo";
import { RoleSwitcher } from "../components/RoleSwitcher";
import { ThemeToggleButton } from "../components/ThemeToggleButton";

export function LoginPage() {
  const { login, loginDemo } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDemo() {
    setError(null);
    setLoading(true);
    try {
      await loginDemo();
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start demo");
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
            Interactive Progress Report
          </div>
          <div className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Sign in to manage your school's progress records
          </div>
        </div>

        <form onSubmit={handleSubmit} className="soft-card p-6">
          <label className="block">
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
          <label className="mt-4 block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Password</span>
            <input
              type="password"
              required
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
            Sign in
          </button>
        </form>

        <div className="my-5 flex items-center gap-3">
          <div className="h-px flex-1" style={{ background: "var(--border)" }} />
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>or</span>
          <div className="h-px flex-1" style={{ background: "var(--border)" }} />
        </div>

        <button
          onClick={handleDemo}
          disabled={loading}
          className="w-full rounded-full border px-4 py-2.5 text-sm font-semibold shadow-sm disabled:opacity-50"
          style={{ borderColor: "transparent", color: "var(--accent-gold)", background: "var(--accent-gold-soft)" }}
        >
          Try the demo — no account needed
        </button>

        <p className="mt-6 text-center text-sm" style={{ color: "var(--text-secondary)" }}>
          New here?{" "}
          <Link to="/signup" className="font-semibold" style={{ color: "var(--accent)" }}>
            Create an account
          </Link>
        </p>
        <RoleSwitcher />
      </div>
    </div>
  );
}
