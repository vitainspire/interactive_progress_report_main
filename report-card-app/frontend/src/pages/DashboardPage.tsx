import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { DotsIcon, InboxIcon, PlusIcon, SearchIcon, SheetIcon, TrashIcon } from "../components/Icons";
import type { BatchSummary } from "../types";

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
  return (
    <article
      className="soft-card reveal group relative flex flex-col p-5 transition-all duration-200 hover:shadow-lg"
      style={{ borderColor: "var(--border)" }}
    >
      <Link to={`/batches/${batch.id}`} className="flex items-start gap-3 focus:outline-none">
        <span className="icon-chip shrink-0">
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

      <div className="mt-4 flex items-center justify-between border-t pt-3" style={{ borderColor: "var(--border)" }}>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          Uploaded {relativeTime(batch.created_at)}
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

  useEffect(() => {
    api
      .get<BatchSummary[]>("/batches")
      .then(setBatches)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your uploads"));
  }, []);

  async function handleDelete(id: number) {
    const batch = batches?.find((b) => b.id === id);
    if (!confirm(`Delete "${batch?.name ?? "this upload"}"? This can't be undone.`)) return;
    await api.del(`/batches/${id}`);
    setBatches((prev) => prev?.filter((b) => b.id !== id) ?? prev);
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
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
            Your uploads
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Every sheet you've uploaded — open one to pick students and print report cards.
          </p>
        </div>
        <Link
          to="/upload"
          className="accent-fill flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all duration-200 active:scale-[0.99]"
        >
          <PlusIcon size={15} />
          New upload
        </Link>
      </header>

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
              className="rounded-xl border px-3 py-2 text-sm font-medium"
              style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
            >
              <option value="recent">Most recent</option>
              <option value="alphabetical">Alphabetical</option>
            </select>
          </div>
        </>
      )}

      {batches && batches.length === 0 && (
        <div className="soft-card mt-5 flex flex-col items-center p-10 text-center">
          <span className="icon-chip" style={{ width: "3rem", height: "3rem" }}>
            <InboxIcon size={22} />
          </span>
          <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            No uploads yet
          </p>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            Upload your first sheet to start generating report cards.
          </p>
          <Link
            to="/upload"
            className="accent-fill mt-4 rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all duration-200"
          >
            Upload your first sheet
          </Link>
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
