import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, continueReferenceDocumentSync } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { FolderIcon } from "../components/Icons";
import { DriveDuplicateResolver } from "../components/DriveDuplicateResolver";
import { isGooglePickerConfigured, pickGoogleSheet, preloadGooglePicker } from "../integrations/googlePicker";
import type { BatchSummary, DriveImportFolderResult } from "../types";

type Mode = "file" | "link" | "drive" | "folder";

export function UploadPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [sheetUrl, setSheetUrl] = useState("");
  const [folderUrl, setFolderUrl] = useState("");
  const [folderResults, setFolderResults] = useState<DriveImportFolderResult | null>(null);
  const [name, setName] = useState("");
  const [schoolName, setSchoolName] = useState(user?.default_school_name ?? "");
  const [classLevel, setClassLevel] = useState("10");
  const [showExamPattern, setShowExamPattern] = useState(false);
  const [totalFaExams, setTotalFaExams] = useState(4);
  const [totalSaExams, setTotalSaExams] = useState(2);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [picking, setPicking] = useState(false);
  const [importStatusMessage, setImportStatusMessage] = useState<string | null>(null);
  const [referenceDocsFoundCount, setReferenceDocsFoundCount] = useState(0);

  const driveEnabled = isGooglePickerConfigured();

  useEffect(() => {
    if (driveEnabled) preloadGooglePicker().catch(() => {});
  }, [driveEnabled]);

  const canSubmit = mode === "link" ? sheetUrl.trim().length > 0 : mode === "folder" ? folderUrl.trim().length > 0 : !!file;

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
    setFolderResults(null);
    setReferenceDocsFoundCount(0);
    setBusy(true);
    try {
      if (mode === "folder") {
        setImportStatusMessage("Reading your folder — this can take a few minutes for folders with many files. Please don't close this tab.");
        const result = await api.post<DriveImportFolderResult>("/batches/import-folder", {
          folder_url: folderUrl.trim(),
          school_name: schoolName.trim() || undefined,
          class_level: classLevel,
          total_fa_exams: totalFaExams,
          total_sa_exams: totalSaExams,
        });
        setFolderResults(result);
        let refDocCount = result.reference_documents.length;
        if (result.reference_documents_remaining > 0) {
          setImportStatusMessage(`Processed ${refDocCount} document${refDocCount === 1 ? "" : "s"} so far, still working — please don't close this tab.`);
          refDocCount += await continueReferenceDocumentSync(result.folder_id, result.reference_documents_remaining, (processedSoFar) =>
            setImportStatusMessage(`Processed ${refDocCount + processedSoFar} document${refDocCount + processedSoFar === 1 ? "" : "s"} so far, still working — please don't close this tab.`),
          );
        }
        setReferenceDocsFoundCount(refDocCount);
        return;
      }
      const form = new FormData();
      if (mode !== "link" && file) form.append("file", file);
      if (mode === "link") form.append("sheet_url", sheetUrl.trim());
      if (name.trim()) form.append("name", name.trim());
      if (schoolName.trim()) form.append("school_name", schoolName.trim());
      form.append("class_level", classLevel);
      form.append("total_fa_exams", String(totalFaExams));
      form.append("total_sa_exams", String(totalSaExams));
      const batch = await api.upload<BatchSummary>("/batches/upload", form);
      navigate(`/batches/${batch.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read this sheet");
    } finally {
      setBusy(false);
      setImportStatusMessage(null);
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
        Upload a sheet
      </h1>
      <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
        Expected layout: three header rows — exam names, subject names, then "Marks"/"Grade" sub-labels — one row per
        student below, with optional RANK and ATTENDANCE columns. Grades A1–D1 count as a pass, D2 as a fail.{" "}
        <a href={api.uploadTemplateUrl()} className="font-semibold hover:underline" style={{ color: "var(--accent)" }}>
          Download a template
        </a>{" "}
        to see it filled in with sample students.
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
        <button
          type="button"
          onClick={() => setMode("folder")}
          className="flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition-colors"
          style={mode === "folder" ? { background: "var(--accent-soft)", color: "var(--accent)" } : { color: "var(--text-secondary)" }}
        >
          <FolderIcon size={14} />
          Drive folder (one class per file)
        </button>
      </div>

      <form onSubmit={onSubmit} className="soft-card mt-3 space-y-4 p-6">
        <div>
          <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
            School name (shown on every card)
          </label>
          <input type="text" value={schoolName} onChange={(e) => setSchoolName(e.target.value)} placeholder="e.g. S.P.P. High School, Gurajanapalli" />
        </div>
        {mode !== "folder" && (
          <div>
            <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Batch name (optional — defaults to the filename)
            </label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Class 9 - Section A" />
          </div>
        )}
        <div>
          <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Class
          </label>
          <select
            value={classLevel}
            onChange={(e) => setClassLevel(e.target.value)}
            className="w-full rounded-md border px-3 py-2.5 text-sm"
            style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
          >
            {["6", "7", "8", "9", "10"].map((c) => (
              <option key={c} value={c}>
                {c}th
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
            Picks which class's real syllabus the AI study plan uses for this batch's students.
          </p>
        </div>

        <div>
          <button
            type="button"
            onClick={() => setShowExamPattern((v) => !v)}
            className="text-xs font-semibold"
            style={{ color: "var(--accent)" }}
          >
            {showExamPattern ? "▾" : "▸"} This school's exam pattern is different from FA×4 + SA×2
          </button>
          {showExamPattern && (
            <div className="mt-2 flex flex-wrap gap-3">
              <div className="w-36">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  FA exams per year
                </label>
                <input
                  type="number"
                  min={0}
                  value={totalFaExams}
                  onChange={(e) => setTotalFaExams(Math.max(0, Number(e.target.value)))}
                />
              </div>
              <div className="w-36">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  SA exams per year
                </label>
                <input
                  type="number"
                  min={0}
                  value={totalSaExams}
                  onChange={(e) => setTotalSaExams(Math.max(0, Number(e.target.value)))}
                />
              </div>
              <p className="w-full text-xs" style={{ color: "var(--text-muted)" }}>
                Used only to predict which syllabus chapters a student's next exam is likely to cover — leave as 4
                and 2 unless this school runs a different number of exams.
              </p>
            </div>
          )}
        </div>

        {mode === "file" && (
          <div>
            <label
              className="block cursor-pointer rounded-lg border-2 border-dashed p-6 text-center"
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
          <div className="rounded-lg border-2 border-dashed p-6 text-center" style={{ borderColor: "var(--accent)" }}>
            <button
              type="button"
              onClick={browseGoogleDrive}
              disabled={picking}
              className="accent-fill rounded-md px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
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

        {mode === "folder" && (
          <div>
            <label className="text-sm" style={{ color: "var(--text-secondary)" }}>
              Google Drive folder link
            </label>
            <input
              type="text"
              value={folderUrl}
              onChange={(e) => setFolderUrl(e.target.value)}
              placeholder="https://drive.google.com/drive/folders/..."
            />
            <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
              Creates one batch per Google Sheet/.xlsx/.csv file found directly inside the folder — e.g. a "Grade
              6.xlsx", "Grade 7.xlsx" per class. The folder and every file in it must be shared as{" "}
              <b>"Anyone with the link can view"</b>. It guesses each file's class from its name (e.g. "Grade 7",
              "9th Class"); the "Class" picked above is only the fallback for a file whose name doesn't say.
            </p>
          </div>
        )}

        {importStatusMessage && (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {importStatusMessage}
          </p>
        )}

        {error && (
          <p className="rounded-lg p-3 text-sm" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
            {error}{" "}
            <a href={api.uploadTemplateUrl()} className="font-semibold underline">
              Download the template
            </a>{" "}
            to see the expected layout.
          </p>
        )}

        {folderResults && (
          <div className="space-y-1.5 rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
            {folderResults.results.map((r) =>
              r.status === "possible_duplicate" ? (
                <DriveDuplicateResolver
                  key={r.file_name}
                  result={r}
                  onResolved={() =>
                    setFolderResults((prev) => (prev ? { ...prev, results: prev.results.filter((x) => x !== r) } : prev))
                  }
                />
              ) : (
                <div key={r.file_name} className="flex items-center justify-between gap-2 text-sm">
                  <span style={{ color: "var(--text-primary)" }}>{r.file_name}</span>
                  {r.status === "created" && r.batch_id ? (
                    <Link to={`/batches/${r.batch_id}`} className="font-medium hover:underline" style={{ color: "var(--status-good)" }}>
                      Imported ({r.student_count} students) →
                    </Link>
                  ) : (
                    <span style={{ color: "var(--accent-mark)" }}>{r.error || "Failed"}</span>
                  )}
                </div>
              ),
            )}
            {referenceDocsFoundCount > 0 && (
              <p className="pt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
                Also found {referenceDocsFoundCount} syllabus/blueprint document{referenceDocsFoundCount === 1 ? "" : "s"} in this
                folder — review {referenceDocsFoundCount === 1 ? "it" : "them"} from the account menu before{" "}
                {referenceDocsFoundCount === 1 ? "it's" : "they're"} used.
              </p>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={!canSubmit || busy}
          className="accent-fill w-full rounded-md px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
        >
          {busy ? (mode === "folder" ? "Importing…" : "Reading…") : mode === "folder" ? "Import folder" : "Upload"}
        </button>
      </form>
    </div>
  );
}
