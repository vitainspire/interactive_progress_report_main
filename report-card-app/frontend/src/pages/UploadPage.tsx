import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { isGooglePickerConfigured, pickGoogleSheet, preloadGooglePicker } from "../integrations/googlePicker";
import type { BatchSummary } from "../types";

type Mode = "file" | "link" | "drive";

export function UploadPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [sheetUrl, setSheetUrl] = useState("");
  const [name, setName] = useState("");
  const [schoolName, setSchoolName] = useState(user?.default_school_name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [picking, setPicking] = useState(false);

  const driveEnabled = isGooglePickerConfigured();

  useEffect(() => {
    if (driveEnabled) preloadGooglePicker().catch(() => {});
  }, [driveEnabled]);

  const canSubmit = mode === "link" ? sheetUrl.trim().length > 0 : !!file;

  async function browseGoogleDrive() {
    setError(null);
    setPicking(true);
    try {
      const picked = await pickGoogleSheet(
        import.meta.env.VITE_GOOGLE_CLIENT_ID as string,
        import.meta.env.VITE_GOOGLE_API_KEY as string,
      );
      if (picked) {
        setFile(picked);
        setMode("file");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open Google Drive");
    } finally {
      setPicking(false);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    setBusy(true);
    try {
      const form = new FormData();
      if (mode !== "link" && file) form.append("file", file);
      if (mode === "link") form.append("sheet_url", sheetUrl.trim());
      if (name.trim()) form.append("name", name.trim());
      if (schoolName.trim()) form.append("school_name", schoolName.trim());
      const batch = await api.upload<BatchSummary>("/batches/upload", form);
      navigate(`/batches/${batch.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read this sheet");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
        Upload a sheet
      </h1>
      <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
        Expected layout: three header rows — exam names, subject names, then "Marks"/"Grade" sub-labels — one row per
        student below, with optional RANK and ATTENDANCE columns. Grades A1–D1 count as a pass, D2 as a fail.
      </p>

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setMode("file")}
          className="rounded-full px-4 py-2 text-sm font-medium transition-colors"
          style={mode === "file" ? { background: "var(--accent-soft)", color: "var(--accent)" } : { color: "var(--text-secondary)" }}
        >
          Upload a file
        </button>
        {driveEnabled && (
          <button
            type="button"
            onClick={() => setMode("drive")}
            className="rounded-full px-4 py-2 text-sm font-medium transition-colors"
            style={mode === "drive" ? { background: "var(--accent-soft)", color: "var(--accent)" } : { color: "var(--text-secondary)" }}
          >
            Browse Google Sheets
          </button>
        )}
        <button
          type="button"
          onClick={() => setMode("link")}
          className="rounded-full px-4 py-2 text-sm font-medium transition-colors"
          style={mode === "link" ? { background: "var(--accent-soft)", color: "var(--accent)" } : { color: "var(--text-secondary)" }}
        >
          Google Sheets link
        </button>
      </div>

      <form onSubmit={onSubmit} className="soft-card mt-3 space-y-4 p-6">
        <div>
          <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
            School name (shown on every card)
          </label>
          <input type="text" value={schoolName} onChange={(e) => setSchoolName(e.target.value)} placeholder="e.g. S.P.P. High School, Gurajanapalli" />
        </div>
        <div>
          <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Batch name (optional — defaults to the filename)
          </label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Class 9 - Section A" />
        </div>

        {mode === "file" && (
          <div>
            <label
              className="block cursor-pointer rounded-2xl border-2 border-dashed p-6 text-center"
              style={{ borderColor: "var(--accent)", color: "var(--text-primary)" }}
            >
              <input type="file" accept=".xlsx,.csv" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              <b>{file ? file.name : "Tap to choose a file"}</b>
              <br />
              <span className="text-sm" style={{ color: "var(--text-muted)" }}>Excel (.xlsx) or CSV</span>
            </label>
          </div>
        )}

        {mode === "drive" && (
          <div className="rounded-2xl border-2 border-dashed p-6 text-center" style={{ borderColor: "var(--accent)" }}>
            <button
              type="button"
              onClick={browseGoogleDrive}
              disabled={picking}
              className="accent-fill rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
            >
              {picking ? "Opening Google Drive…" : "Browse Google Sheets"}
            </button>
            <p className="mt-3 text-sm" style={{ color: "var(--text-muted)" }}>
              Sign in with Google, then pick a sheet from your Drive — private sheets work too, nothing needs to be
              shared first.
            </p>
            {file && <p className="mt-2 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Selected: {file.name}</p>}
          </div>
        )}

        {mode === "link" && (
          <div>
            <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Google Sheets link
            </label>
            <input
              type="text"
              value={sheetUrl}
              onChange={(e) => setSheetUrl(e.target.value)}
              placeholder="https://docs.google.com/spreadsheets/d/..."
            />
            <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
              The sheet must be shared as <b>"Anyone with the link can view"</b> (Share → General access) — otherwise
              the server can't read it. Nothing about the sheet is changed; it's only read.
            </p>
          </div>
        )}

        {error && (
          <p className="rounded-lg p-3 text-sm" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={!canSubmit || busy}
          className="accent-fill w-full rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
        >
          {busy ? "Reading…" : "Upload"}
        </button>
      </form>
    </div>
  );
}
