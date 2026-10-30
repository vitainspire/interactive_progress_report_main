import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { DotsIcon, FolderIcon, PlusIcon, SearchIcon, SheetIcon, TrashIcon } from "../components/Icons";
import { DriveDuplicateResolver } from "../components/DriveDuplicateResolver";
import type { BatchSummary, DriveImportFileResult, DriveImportFolderResult, DriveSyncFolderResult, SendResult } from "../types";

type SortOrder = "recent" | "alphabetical";

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString();
}

function BatchCard({ batch, onDelete }: { batch: BatchSummary; onDelete: (id: number) => void }) {
  const [subjects, setSubjects] = useState<string[] | null>(null);
  const [subjectsOpen, setSubjectsOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendNote, setSendNote] = useState<string | null>(null);

  async function toggleSubjects() {
    const next = !subjectsOpen;
    setSubjectsOpen(next);
    if (next && subjects === null) {
      try {
        const res = await api.get<{ subjects: string[] }>(`/batches/${batch.id}/subjects`);
        setSubjects(res.subjects);
      } catch {
        setSubjects([]);
      }
    }
  }

  async function sendReports() {
    setSending(true);
    setSendNote(null);
    try {
      const res = await api.post<{ results: SendResult[] }>(`/batches/${batch.id}/send-reports`, { student_ids: null });
      const sent = res.results.filter((r) => r.status === "sent").length;
      setSendNote(`Sent ${sent} of ${res.results.length}.`);
    } catch (err) {
      setSendNote(err instanceof Error ? err.message : "Could not send reports");
    } finally {
      setSending(false);
    }
  }

  return (
    <article
      className="soft-card reveal group relative flex flex-col p-5 transition-transform duration-200 hover:-translate-y-0.5"
      style={{ borderTop: "3px solid var(--accent)" }}
    >
      <Link to={`/batches/${batch.id}`} className="flex items-start gap-3 focus:outline-none">
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
          style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
        >
          <SheetIcon size={16} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-display truncate text-base font-bold" style={{ color: "var(--text-primary)" }}>
            {batch.name}
          </div>
          <div className="truncate text-sm" style={{ color: "var(--text-secondary)" }}>
            {batch.school_name || "No school name set"}
          </div>
        </div>
      </Link>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <span className="pill">{batch.student_count} students</span>
        {batch.exam_codes.map((code) => (
          <span key={code} className="pill">
            {code}
          </span>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={toggleSubjects}
          className="rounded-md border px-2.5 py-1 text-xs font-semibold transition-colors duration-200 hover:bg-[var(--accent-soft)]"
          style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
        >
          {subjectsOpen ? "Hide analysis" : "View analysis"}
        </button>
        <button
          type="button"
          onClick={sendReports}
          disabled={sending}
          className="rounded-md border px-2.5 py-1 text-xs font-semibold transition-colors duration-200 hover:bg-[var(--accent-soft)] disabled:opacity-60"
          style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
        >
          {sending ? "Sending…" : "Send reports"}
        </button>
      </div>

      {subjectsOpen && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {subjects === null && (
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              Loading subjects…
            </span>
          )}
          {subjects && subjects.length === 0 && (
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              No subjects found yet.
            </span>
          )}
          {subjects?.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => window.open(api.subjectAnalysisUrl(batch.id, s), "_blank", "noopener")}
              className="pill transition-colors duration-200 hover:bg-[var(--accent-soft)]"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {sendNote && (
        <p className="mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
          {sendNote}
        </p>
      )}

      <div className="mt-4 flex items-center justify-between border-t pt-3" style={{ borderColor: "var(--border)" }}>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {batch.source_type === "drive_folder_item" && batch.last_synced_at
            ? `Synced ${relativeTime(batch.last_synced_at)}`
            : `Uploaded ${relativeTime(batch.created_at)}`}
        </span>
        <details className="relative">
          <summary
            aria-label="Upload actions"
            className="flex h-7 w-7 cursor-pointer list-none items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-soft)]"
            style={{ color: "var(--text-muted)" }}
          >
            <DotsIcon size={16} />
          </summary>
          <div className="soft-card absolute right-0 z-10 mt-1 w-40 overflow-hidden p-1" style={{ boxShadow: "var(--shadow-pop)" }}>
            <button
              onClick={() => onDelete(batch.id)}
              className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-mark-soft)]"
              style={{ color: "var(--accent-mark)" }}
            >
              <TrashIcon size={14} />
              Delete upload
            </button>
          </div>
        </details>
      </div>
    </article>
  );
}

export function DashboardPage() {
  const [batches, setBatches] = useState<BatchSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortOrder>("recent");
  const [folderUrl, setFolderUrl] = useState("");
  const [settingUp, setSettingUp] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [showFolderGuide, setShowFolderGuide] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [syncNote, setSyncNote] = useState<string | null>(null);
  const [syncDuplicates, setSyncDuplicates] = useState<DriveImportFileResult[]>([]);

  function refreshBatches() {
    return api
      .get<BatchSummary[]>("/batches")
      .then(setBatches)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your uploads"));
  }

  useEffect(() => {
    refreshBatches();
  }, []);

  async function handleDelete(id: number) {
    const batch = batches?.find((b) => b.id === id);
    if (!confirm(`Delete "${batch?.name ?? "this upload"}"? This can't be undone.`)) return;
    await api.del(`/batches/${id}`);
    setBatches((prev) => prev?.filter((b) => b.id !== id) ?? prev);
  }

  // Once any class has been imported from a Drive folder, that folder is
  // this account's linked source — the same one "Sync Drive folder" re-
  // checks for new/updated classes. Schools only ever link one folder in
  // practice, so whichever batch has one is enough to find it.
  const linkedFolderId = useMemo(() => batches?.find((b) => b.source_folder_id)?.source_folder_id ?? null, [batches]);

  async function setUpDriveFolder(e: React.FormEvent) {
    e.preventDefault();
    if (!folderUrl.trim()) return;
    setSettingUp(true);
    setSetupError(null);
    try {
      const result = await api.post<DriveImportFolderResult>("/batches/import-folder", { folder_url: folderUrl.trim() });
      const created = result.results.filter((r) => r.status === "created").length;
      const possibleDuplicates = result.results.filter((r) => r.status === "possible_duplicate");
      setSyncDuplicates(possibleDuplicates);
      if (created === 0 && possibleDuplicates.length === 0) {
        setSetupError("No class sheets were found directly inside that folder.");
      } else {
        await refreshBatches();
      }
    } catch (err) {
      setSetupError(err instanceof Error ? err.message : "Could not read that Drive folder");
    } finally {
      setSettingUp(false);
    }
  }

  async function syncDriveFolder() {
    if (!linkedFolderId) return;
    setSyncing(true);
    setSyncNote(null);
    try {
      const result = await api.post<DriveSyncFolderResult>("/batches/sync-folder", { folder_id: linkedFolderId });
      const created = result.results.filter((r) => r.status === "created").length;
      const synced = result.results.filter((r) => r.status === "synced").length;
      const failed = result.results.filter((r) => r.status === "failed").length;
      const possibleDuplicates = result.results.filter((r) => r.status === "possible_duplicate");
      const bits = [];
      if (created) bits.push(`${created} new class${created === 1 ? "" : "es"}`);
      if (synced) bits.push(`${synced} updated`);
      if (failed) bits.push(`${failed} failed`);
      if (possibleDuplicates.length) bits.push(`${possibleDuplicates.length} need a decision below`);
      setSyncNote(bits.length ? bits.join(", ") : "Already up to date.");
      setSyncDuplicates(possibleDuplicates);
      await refreshBatches();
    } catch (err) {
      setSyncNote(err instanceof Error ? err.message : "Could not sync the Drive folder");
    } finally {
      setSyncing(false);
    }
  }

  const visibleBatches = useMemo(() => {
    if (!batches) return null;
    const filtered = query.trim()
      ? batches.filter((b) => `${b.name} ${b.school_name}`.toLowerCase().includes(query.trim().toLowerCase()))
      : batches;
    const sorted = [...filtered];
    if (sort === "alphabetical") sorted.sort((a, b) => a.name.localeCompare(b.name));
    else sorted.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    return sorted;
  }, [batches, query, sort]);

  const totalStudents = useMemo(() => batches?.reduce((sum, b) => sum + b.student_count, 0) ?? 0, [batches]);

  return (
    <section>
      <nav className="text-xs" style={{ color: "var(--text-muted)" }} aria-label="Breadcrumb">
        <Link to="/tools" className="hover:underline" style={{ color: "var(--text-muted)" }}>
          Tools
        </Link>{" "}
        / Report Card Generator
      </nav>
      <header
        className="dot-grid-plane-dark relative mt-2 flex flex-wrap items-center justify-between gap-4 overflow-hidden rounded-2xl px-6 py-6 sm:px-8 sm:py-7"
        style={{ background: "var(--accent-strong)" }}
      >
        <h1 className="font-serif text-2xl font-medium text-white sm:text-3xl">Your uploads</h1>
        <div className="flex items-center gap-2">
          {linkedFolderId && (
            <button
              type="button"
              onClick={syncDriveFolder}
              disabled={syncing}
              className="flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-semibold text-white transition-colors duration-200 hover:bg-white/10 disabled:opacity-60"
              style={{ borderColor: "rgba(255,255,255,0.35)" }}
            >
              <FolderIcon size={15} />
              {syncing ? "Syncing…" : "Sync Drive folder"}
            </button>
          )}
          <Link
            to="/upload"
            className="flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold shadow-sm transition-all duration-200 active:scale-[0.99]"
            style={{ background: "var(--lp-gold)", color: "var(--accent-strong)" }}
          >
            <PlusIcon size={15} />
            New upload
          </Link>
        </div>
      </header>

      {syncNote && (
        <p className="mt-3 text-sm" style={{ color: "var(--text-secondary)" }}>
          {syncNote} — picks up any class added to the same folder since the last import.
        </p>
      )}

      {syncDuplicates.length > 0 && (
        <div className="mt-2 space-y-1.5">
          {syncDuplicates.map((r) => (
            <DriveDuplicateResolver
              key={r.file_name}
              result={r}
              onResolved={() => {
                setSyncDuplicates((prev) => prev.filter((x) => x !== r));
                refreshBatches();
              }}
            />
          ))}
        </div>
      )}

      {error && <p className="mt-4 text-sm" style={{ color: "var(--accent-mark)" }}>{error}</p>}

      {batches && batches.length > 0 && (
        <>
          <div className="mt-5 flex flex-wrap items-center gap-2 text-sm" style={{ color: "var(--text-secondary)" }}>
            <span className="pill">Total sheets: {batches.length}</span>
            <span className="pill">Total students: {totalStudents}</span>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div className="relative max-w-xs flex-1">
              <span
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
                style={{ color: "var(--text-muted)" }}
              >
                <SearchIcon size={15} />
              </span>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search sheets or schools…"
                aria-label="Search uploads"
                className="pl-9"
              />
            </div>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortOrder)}
              aria-label="Sort uploads"
              className="rounded-md border px-3 py-2 text-sm font-medium"
              style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
            >
              <option value="recent">Most recent</option>
              <option value="alphabetical">Alphabetical</option>
            </select>
          </div>
        </>
      )}

      {batches && batches.length === 0 && (
        <div className="soft-card mt-5 flex flex-col items-center p-10 text-center" style={{ borderTop: "3px solid var(--accent)" }}>
          <span
            className="flex h-14 w-14 items-center justify-center rounded-2xl"
            style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
          >
            <FolderIcon size={24} />
          </span>
          <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            Set up your Drive folder
          </p>
          <p className="mx-auto mt-1 max-w-sm text-sm" style={{ color: "var(--text-secondary)" }}>
            Paste the link to the Drive folder where this school keeps its class mark sheets — one file per class.
            Every class in it becomes a sheet here, and adding a class to that same folder later picks it up
            automatically with "Sync Drive folder". Not sure of the layout each sheet needs?{" "}
            <a href={api.uploadTemplateUrl()} className="font-semibold hover:underline" style={{ color: "var(--accent)" }}>
              Download a template
            </a>
            . Not sure how to set up the folder itself?{" "}
            <button
              type="button"
              onClick={() => setShowFolderGuide((v) => !v)}
              className="font-semibold hover:underline"
              style={{ color: "var(--accent)" }}
            >
              {showFolderGuide ? "Hide folder guide" : "How to set up your folder"}
            </button>
          </p>

          {showFolderGuide && (
            <div
              className="mx-auto mt-3 max-w-sm rounded-lg p-4 text-left text-sm"
              style={{ background: "var(--accent-soft)", color: "var(--text-primary)" }}
            >
              <p className="font-semibold">Inside that one Drive folder:</p>
              <ul className="mt-2 list-disc space-y-1.5 pl-4" style={{ color: "var(--text-secondary)" }}>
                <li>Required: one mark-sheet file per class — e.g. "Class 10.xlsx", "Class 9.xlsx".</li>
                <li>
                  Optional: each subject's syllabus or exam-blueprint document (a PDF or a clear photo) — not needed,
                  but adding these makes the Study Plan and Subject Analysis features more accurate. Name it
                  something like "10 Maths Syllabus" or "10 Science Blueprint" so it's easy to tell apart.
                </li>
                <li>No sub-folders needed — everything goes loose in this one folder, and the app sorts it out.</li>
                <li>Once it's processed, you'll see every file listed by its name so you can check it came through correctly.</li>
              </ul>
            </div>
          )}

          <form onSubmit={setUpDriveFolder} className="mt-4 flex w-full max-w-sm flex-col gap-2">
            <input
              type="text"
              value={folderUrl}
              onChange={(e) => setFolderUrl(e.target.value)}
              placeholder="https://drive.google.com/drive/folders/..."
            />
            <button
              type="submit"
              disabled={settingUp || !folderUrl.trim()}
              className="accent-fill rounded-md px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all duration-200 disabled:opacity-60"
            >
              {settingUp ? "Setting up…" : "Set up Drive folder"}
            </button>
          </form>
          {setupError && (
            <p className="mt-2 text-sm" style={{ color: "var(--accent-mark)" }}>
              {setupError}
            </p>
          )}
          <p className="mt-4 text-xs" style={{ color: "var(--text-muted)" }}>
            Only have one class, or not using Drive?{" "}
            <Link to="/upload" className="font-medium hover:underline" style={{ color: "var(--accent)" }}>
              Upload a single sheet instead
            </Link>
          </p>
        </div>
      )}

      {visibleBatches && visibleBatches.length > 0 && (
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visibleBatches.map((b) => (
            <BatchCard key={b.id} batch={b} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {batches && batches.length > 0 && visibleBatches && visibleBatches.length === 0 && (
        <p className="mt-6 text-center text-sm" style={{ color: "var(--text-muted)" }}>
          No uploads match "{query}".
        </p>
      )}
    </section>
  );
}
