import { useState } from "react";
import { api } from "../api/client";
import type { TtImportConfirmResult, TtImportPreview } from "../types";
import { FolderIcon } from "./Icons";

/** Lets a school that already has a built timetable (an Excel "master
 * sheet" grid — see app/parsing/timetable_parser.py) upload it instead of
 * recreating it from scratch with Generate. The short subject/teacher
 * codes the file actually used (e.g. "PS", "KSVL") are never auto-matched
 * to a real subject name or a teacher's full name/phone — a wrong guess
 * there is a real safety issue (a substitute alert texting the wrong
 * person), so a human always fills those in here before confirming. */
export function TimetableImportPanel({ onImported }: { onImported: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<TtImportPreview | null>(null);
  const [subjectNames, setSubjectNames] = useState<Record<string, string>>({});
  const [teacherInfo, setTeacherInfo] = useState<Record<string, { name: string; phone: string }>>({});
  const [result, setResult] = useState<TtImportConfirmResult | null>(null);

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.upload<TtImportPreview>("/timetable/import", form);
      setPreview(res);
      setSubjectNames(Object.fromEntries(res.subject_codes.map((c) => [c, c])));
      setTeacherInfo(Object.fromEntries(res.teacher_codes.map((c) => [c, { name: c, phone: "" }])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read that file");
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport() {
    if (!preview) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<TtImportConfirmResult>("/timetable/import/confirm", {
        grid: preview.grid,
        subjects: subjectNames,
        teachers: teacherInfo,
      });
      setResult(res);
      setPreview(null);
      onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not import this timetable");
    } finally {
      setBusy(false);
    }
  }

  function close() {
    setOpen(false);
    setPreview(null);
    setResult(null);
    setError(null);
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-semibold transition-colors duration-200 hover:bg-[var(--accent-soft)]"
        style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
      >
        <FolderIcon size={15} />
        Import existing timetable
      </button>
    );
  }

  return (
    <div className="soft-card mt-3 w-full p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          Import your existing timetable
        </h3>
        <button type="button" onClick={close} className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
          Close
        </button>
      </div>
      <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
        Already have a timetable built outside this app? Upload the Excel file with your weekly schedule — one sheet
        with every class's day-by-day periods — instead of building it from scratch here.
      </p>

      {!preview && !result && (
        <div className="mt-3">
          <input type="file" accept=".xlsx" onChange={onPickFile} disabled={busy} />
          {busy && (
            <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
              Reading…
            </p>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-xs" style={{ color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}

      {result && (
        <p className="mt-3 rounded-lg p-3 text-sm" style={{ background: "var(--status-good-soft)", color: "var(--status-good)" }}>
          Imported {result.classes_imported} classes, {result.periods_imported} periods — your timetable is ready.
        </p>
      )}

      {preview && (
        <div className="mt-3 space-y-4">
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Found {preview.classes.length} classes: {preview.classes.map((c) => c.label).join(", ")}. Name the real
            subjects and teachers behind each short code below before confirming — nothing is guessed for you.
          </p>

          <div>
            <h4 className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Subjects
            </h4>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {preview.subject_codes.map((code) => (
                <div key={code} className="flex items-center gap-2">
                  <span
                    className="w-16 flex-none rounded-md px-2 py-1.5 text-center text-xs font-bold"
                    style={{ background: "var(--surface-2)", color: "var(--text-secondary)" }}
                  >
                    {code}
                  </span>
                  <input
                    type="text"
                    value={subjectNames[code] ?? ""}
                    onChange={(e) => setSubjectNames((s) => ({ ...s, [code]: e.target.value }))}
                    placeholder="Subject name"
                    className="flex-1"
                  />
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Teachers
            </h4>
            <div className="mt-2 space-y-2">
              {preview.teacher_codes.map((code) => (
                <div key={code} className="flex flex-wrap items-center gap-2">
                  <span
                    className="w-16 flex-none rounded-md px-2 py-1.5 text-center text-xs font-bold"
                    style={{ background: "var(--surface-2)", color: "var(--text-secondary)" }}
                  >
                    {code}
                  </span>
                  <input
                    type="text"
                    value={teacherInfo[code]?.name ?? ""}
                    onChange={(e) => setTeacherInfo((t) => ({ ...t, [code]: { ...t[code], name: e.target.value } }))}
                    placeholder="Full name"
                    className="min-w-40 flex-1"
                  />
                  <input
                    type="text"
                    value={teacherInfo[code]?.phone ?? ""}
                    onChange={(e) => setTeacherInfo((t) => ({ ...t, [code]: { ...t[code], phone: e.target.value } }))}
                    placeholder="Phone (optional)"
                    className="w-36"
                  />
                </div>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={confirmImport}
            disabled={busy}
            className="accent-fill rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Importing…" : "Confirm import"}
          </button>
        </div>
      )}
    </div>
  );
}
