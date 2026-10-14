import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { AccountsResponse, StudentAccount } from "../types";

/** Admin-only widget on a student's detail page: lets the headmaster set up
 * (or reset) that student's own roll-number + PIN login, without needing a
 * separate student picker — it's cheapest to manage right where the
 * headmaster is already looking at that one student. */
export function StudentLoginPanel({ studentId }: { studentId: number }) {
  const { user } = useAuth();
  const [account, setAccount] = useState<StudentAccount | null | undefined>(undefined);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setAccount(undefined);
    api
      .get<AccountsResponse>("/accounts")
      .then((res) => setAccount(res.students.find((s) => s.student_id === studentId) ?? null))
      .catch(() => setAccount(null));
  }, [studentId]);

  async function createLogin(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const created = await api.post<{ roll_no: string }>("/accounts/students", { student_id: studentId, pin });
      setAccount({ id: 0, display_name: "", roll_no: created.roll_no, student_id: studentId, section: "", class_id: 0 });
      setPin("");
      setMessage(`Login created — roll number ${created.roll_no}. Share it with the school code (${user?.school_code}) and this PIN.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not create login");
    } finally {
      setBusy(false);
    }
  }

  async function resetPin(e: React.FormEvent) {
    e.preventDefault();
    if (!account) return;
    setBusy(true);
    setMessage(null);
    try {
      await api.post(`/accounts/students/${account.id}/reset-pin`, { pin });
      setPin("");
      setMessage("PIN updated.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Could not update PIN");
    } finally {
      setBusy(false);
    }
  }

  if (account === undefined) return null;

  return (
    <div className="mt-3 inline-flex flex-col gap-2 rounded-xl border p-3 text-xs" style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}>
      {account ? (
        <form onSubmit={resetPin} className="flex flex-wrap items-center gap-2">
          <span style={{ color: "var(--text-secondary)" }}>
            Login roll number: <strong style={{ color: "var(--text-primary)" }}>{account.roll_no}</strong> · school code{" "}
            <strong style={{ color: "var(--text-primary)" }}>{user?.school_code}</strong>
          </span>
          <input
            type="password"
            required
            minLength={4}
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="New PIN"
            className="w-24 rounded-lg border px-2 py-1 text-xs"
            style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-full border px-3 py-1 text-xs font-medium disabled:opacity-50"
            style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
          >
            Reset PIN
          </button>
        </form>
      ) : (
        <form onSubmit={createLogin} className="flex flex-wrap items-center gap-2">
          <span style={{ color: "var(--text-secondary)" }}>No student login yet.</span>
          <input
            type="password"
            required
            minLength={4}
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            placeholder="Set a PIN"
            className="w-24 rounded-lg border px-2 py-1 text-xs"
            style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-full border px-3 py-1 text-xs font-medium disabled:opacity-50"
            style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
          >
            Create login
          </button>
        </form>
      )}
      {message && <span style={{ color: "var(--text-secondary)" }}>{message}</span>}
    </div>
  );
}
