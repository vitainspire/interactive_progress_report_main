import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Settings } from "../types";

const FIELDS: { key: keyof Settings; label: string; placeholder: string }[] = [
  { key: "school_name", label: "School name", placeholder: "S.P.P.Z.P.P. High School, Gurajanapalli" },
  { key: "school_udise", label: "UDISE code", placeholder: "28143601909" },
  { key: "headmaster_name", label: "Headmaster name", placeholder: "" },
  { key: "headmaster_phone", label: "Headmaster phone", placeholder: "" },
];

export function SettingsPage() {
  const { user } = useAuth();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get<Settings>("/settings").then(setSettings);
  }, []);

  if (!settings) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  async function save() {
    if (!settings) return;
    await api.put<Settings>("/settings", settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
        Settings
      </h1>
      <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
        These details aren't in the spreadsheet, so set them here — they're used on the generated report cards.
        Looking for the class name/label? That's managed per class now, under{" "}
        <Link to="/manage-classes" style={{ color: "var(--accent)" }}>
          Classes
        </Link>
        .
      </p>

      {user?.is_demo && (
        <p className="mt-3 rounded-full px-3 py-1.5 text-xs font-medium" style={{ background: "var(--accent-gold-soft)", color: "var(--accent-gold)" }}>
          Settings are read-only on the shared demo account.
        </p>
      )}

      <div className="soft-card mt-4 space-y-4 p-6">
        {FIELDS.map((f) => (
          <label key={f.key} className="block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
              {f.label}
            </span>
            <input
              value={settings[f.key]}
              placeholder={f.placeholder}
              disabled={user?.is_demo}
              onChange={(e) => setSettings({ ...settings, [f.key]: e.target.value })}
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm disabled:opacity-60"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
        ))}
      </div>

      <button
        onClick={save}
        disabled={user?.is_demo}
        className="gradient-fill mt-4 rounded-full px-5 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-50"
      >
        Save
      </button>
      {saved && (
        <span className="ml-3 text-sm font-medium" style={{ color: "var(--status-good)" }}>
          Saved ✓
        </span>
      )}
    </div>
  );
}
