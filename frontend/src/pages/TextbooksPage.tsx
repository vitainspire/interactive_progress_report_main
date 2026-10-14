import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Meta, Textbook, TextbookTopic } from "../types";

function subjectLabel(s: string): string {
  return s.charAt(0) + s.slice(1).toLowerCase();
}

/** One subject's row: upload (or replace) its textbook PDF, and once a
 * table of contents has been extracted, review/edit the chapter list —
 * the heuristic TOC scan can miss or garble the odd line, so nothing here
 * is locked in until the admin has looked at it. */
function TextbookRow({ classId, subject, textbook, onChange }: { classId: number; subject: string; textbook: Textbook | undefined; onChange: () => void }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topics, setTopics] = useState<TextbookTopic[]>(textbook?.topics ?? []);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setTopics(textbook?.topics ?? []);
    setDirty(false);
  }, [textbook]);

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    try {
      await api.upload<Textbook>(`/textbooks?class_id=${classId}&subject=${encodeURIComponent(subject)}`, file);
      setExpanded(true);
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  function updateTitle(i: number, title: string) {
    setTopics((prev) => prev.map((t, idx) => (idx === i ? { ...t, title } : t)));
    setDirty(true);
  }

  function removeTopic(i: number) {
    setTopics((prev) => prev.filter((_, idx) => idx !== i));
    setDirty(true);
  }

  function addTopic() {
    setTopics((prev) => [...prev, { chapter_no: null, title: "", page: null }]);
    setDirty(true);
  }

  async function saveTopics() {
    setSaving(true);
    setError(null);
    try {
      await api.put<Textbook>(`/textbooks/${subject}/topics?class_id=${classId}`, { topics: topics.filter((t) => t.title.trim()) });
      setDirty(false);
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save changes");
    } finally {
      setSaving(false);
    }
  }

  async function removeTextbook() {
    if (!confirm(`Remove the ${subjectLabel(subject)} textbook?`)) return;
    await api.del(`/textbooks/${subject}?class_id=${classId}`);
    onChange();
  }

  return (
    <div className="soft-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{subjectLabel(subject)}</div>
          {textbook ? (
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>
              {textbook.filename} · {textbook.topics.length} chapter{textbook.topics.length === 1 ? "" : "s"} found
            </div>
          ) : (
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>No textbook uploaded yet.</div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {textbook && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="rounded-full border px-3 py-1.5 text-xs font-medium"
              style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
            >
              {expanded ? "Hide chapters" : "Review chapters"}
            </button>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
          <button
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="gradient-fill rounded-full px-3.5 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
          >
            {uploading ? "Reading PDF…" : textbook ? "Replace PDF" : "Upload PDF"}
          </button>
          {textbook && (
            <button
              onClick={removeTextbook}
              className="rounded-full border px-3 py-1.5 text-xs font-medium"
              style={{ borderColor: "var(--border)", color: "var(--accent-mark)" }}
            >
              Remove
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="mt-2 rounded-xl p-2 text-xs" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}

      {expanded && textbook && (
        <div className="mt-3 space-y-1.5 border-t pt-3" style={{ borderColor: "var(--border)" }}>
          {topics.length === 0 && (
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              No chapters found automatically — add them below.
            </p>
          )}
          {topics.map((t, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-6 shrink-0 text-right font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                {t.chapter_no ?? i + 1}.
              </span>
              <input
                value={t.title}
                onChange={(e) => updateTitle(i, e.target.value)}
                className="flex-1 rounded-lg border px-2.5 py-1.5 text-sm"
                style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
              />
              <button
                onClick={() => removeTopic(i)}
                aria-label="Remove chapter"
                className="shrink-0 rounded-full border px-2 py-1 text-xs"
                style={{ borderColor: "var(--border)", color: "var(--accent-mark)" }}
              >
                ✕
              </button>
            </div>
          ))}
          <div className="flex items-center gap-2 pt-1">
            <button onClick={addTopic} className="text-xs font-medium" style={{ color: "var(--accent)" }}>
              + Add chapter
            </button>
            {dirty && (
              <button
                onClick={saveTopics}
                disabled={saving}
                className="ml-auto rounded-full border px-3 py-1 text-xs font-semibold disabled:opacity-50"
                style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
              >
                Save changes
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function TextbooksPage() {
  const classId = Number(useParams().classId);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [textbooks, setTextbooks] = useState<Textbook[] | null>(null);

  function reload() {
    api.get<Textbook[]>(`/textbooks?class_id=${classId}`).then(setTextbooks);
  }

  useEffect(() => {
    setMeta(null);
    setTextbooks(null);
    api.get<Meta>(`/meta?class_id=${classId}`).then(setMeta);
    reload();
  }, [classId]);

  if (!meta || !textbooks) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  const bySubject = new Map(textbooks.map((t) => [t.subject, t]));

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div>
        <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          Textbooks
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Upload each subject's textbook PDF. The chapter list is read from its index (first few pages) and used to
          suggest focus chapters wherever a student is shown as failing that subject — on their report page, the
          printed report card, and the Ask bar.
        </p>
      </div>

      {meta.subjects.length === 0 ? (
        <p className="soft-card p-4 text-sm" style={{ color: "var(--text-muted)" }}>
          Upload a progress sheet first — subjects come from the exam data.
        </p>
      ) : (
        <div className="space-y-3">
          {meta.subjects.map((s) => (
            <TextbookRow key={s} classId={classId} subject={s} textbook={bySubject.get(s)} onChange={reload} />
          ))}
        </div>
      )}
    </div>
  );
}
