import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Logo } from "../components/Logo";
import { RoleSwitcher } from "../components/RoleSwitcher";
import { ThemeToggleButton } from "../components/ThemeToggleButton";

export function StudentLoginPage() {
  const { loginStudent } = useAuth();
  const navigate = useNavigate();
  const [schoolCode, setSchoolCode] = useState("");
  const [rollNo, setRollNo] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await loginStudent(schoolCode, rollNo, pin);
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
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
            Student login
          </div>
          <div className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Ask your teacher for your school code, roll number, and PIN
          </div>
        </div>

        <form onSubmit={handleSubmit} className="soft-card p-6">
          <label className="block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>School code</span>
            <input
              required
              value={schoolCode}
              onChange={(e) => setSchoolCode(e.target.value)}
              placeholder="e.g. A1B2C3"
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm uppercase"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
          <label className="mt-4 block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Roll number</span>
            <input
              required
              value={rollNo}
              onChange={(e) => setRollNo(e.target.value)}
              placeholder="e.g. A-12"
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm uppercase"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
          <label className="mt-4 block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>PIN</span>
            <input
              type="password"
              required
              value={pin}
              onChange={(e) => setPin(e.target.value)}
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
        <RoleSwitcher />

      </div>
    </div>
  );
}
