import { useState } from "react";
import { ApiError, api } from "../api/client";
import type { BlueprintTopicDraft, ReferenceDocument, ReferenceDocumentExtraction, SyllabusChapterDraft } from "../types";

function emptyExtraction(): ReferenceDocumentExtraction {
  return { subject_guess: "", class_level_guess: "", document_type: "unknown", chapters: [], topics: [], exam_format: "", tips: [] };
}

export function ReferenceDocumentReview({ doc, onChanged }: { doc: ReferenceDocument; onChanged: () => void }) {
  const [draft, setDraft] = useState<ReferenceDocumentExtraction>(doc.extracted ?? emptyExtraction());
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function saveDraft() {
    setSaving(true);
    setError(null);
    try {
      await api.put(`/reference-documents/${doc.id}`, draft);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save your edits");
    } finally {
      setSaving(false);
    }
  }

  async function confirm(force = false) {
    setConfirming(true);
    setError(null);
    try {
      await saveDraft();
      await api.post(`/reference-documents/${doc.id}/confirm${force ? "?force=true" : ""}`, undefined);
      onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        if (window.confirm(`${err.message}\n\nReplace it?`)) {
          return confirm(true);
        }
        return;
      }
      setError(err instanceof Error ? err.message : "Could not confirm this document");
    } finally {
      setConfirming(false);
    }
  }

  async function reject() {
    setConfirming(true);
    setError(null);
    try {
      await api.post(`/reference-documents/${doc.id}/reject`, undefined);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not dismiss this document");
    } finally {
      setConfirming(false);
    }
  }

  function updateChapter(idx: number, patch: Partial<SyllabusChapterDraft>) {
    setDraft((d) => ({ ...d, chapters: d.chapters.map((c, i) => (i === idx ? { ...c, ...patch } : c)) }));
  }

  function removeChapter(idx: number) {
    setDraft((d) => ({ ...d, chapters: d.chapters.filter((_, i) => i !== idx) }));
  }

  function addChapter() {
    setDraft((d) => ({ ...d, chapters: [...d.chapters, { chapter_no: d.chapters.length + 1, chapter_name: "" }] }));
  }

  function updateTopic(idx: number, patch: Partial<BlueprintTopicDraft>) {
    setDraft((d) => ({ ...d, topics: d.topics.map((t, i) => (i === idx ? { ...t, ...patch } : t)) }));
  }

  function removeTopic(idx: number) {
    setDraft((d) => ({ ...d, topics: d.topics.filter((_, i) => i !== idx) }));
  }

  function addTopic() {
    setDraft((d) => ({ ...d, topics: [...d.topics, { topic_name: "", marks: 0 }] }));
  }

  if (doc.status === "failed") {
    return (
      <div className="soft-card p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            {doc.file_name}
          </p>
          <button
            type="button"
            onClick={reject}
            disabled={confirming}
            className="flex-none rounded-md border px-2.5 py-1 text-xs font-semibold disabled:opacity-60"
            style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
          >
            {confirming ? "Working…" : "Dismiss"}
          </button>
        </div>
        <p className="mt-1 text-xs" style={{ color: "var(--accent-mark)" }}>
          Couldn't read this document: {doc.error || "unknown error"}. Try re-uploading it as a clearer scan or photo.
        </p>
        {error && (
          <p className="mt-1 text-xs" style={{ color: "var(--accent-mark)" }}>
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="soft-card space-y-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {doc.file_name}
        </p>
        <span className="pill">{doc.status}</span>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="w-40">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Subject
          </label>
          <input
            type="text"
            value={draft.subject_guess ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, subject_guess: e.target.value }))}
            placeholder="e.g. Telugu"
          />
        </div>
        <div className="w-28">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Class
          </label>
          <input
            type="text"
            value={draft.class_level_guess ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, class_level_guess: e.target.value }))}
            placeholder="e.g. 10"
          />
        </div>
        <div className="w-40">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Document type
          </label>
          <select
            value={draft.document_type}
            onChange={(e) => setDraft((d) => ({ ...d, document_type: e.target.value as ReferenceDocumentExtraction["document_type"] }))}
            className="w-full rounded-md border px-2.5 py-1.5 text-sm"
            style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
          >
            <option value="unknown">Unknown</option>
            <option value="syllabus">Syllabus (chapter list)</option>
            <option value="blueprint">Exam blueprint (marks weightage)</option>
          </select>
        </div>
      </div>

      {draft.document_type === "syllabus" && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Chapters
          </p>
          <div className="mt-1.5 space-y-1.5">
            {draft.chapters.map((c, idx) => (
              <div key={idx} className="flex flex-wrap items-center gap-1.5">
                <input
                  type="number"
                  value={c.chapter_no}
                  onChange={(e) => updateChapter(idx, { chapter_no: Number(e.target.value) })}
                  className="w-14 rounded-md border px-2 py-1 text-xs"
                  style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
                />
                <input
                  type="text"
                  value={c.chapter_name}
                  onChange={(e) => updateChapter(idx, { chapter_name: e.target.value })}
                  placeholder="Chapter name"
                  className="flex-1 rounded-md border px-2 py-1 text-xs"
                  style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
                />
                <button type="button" onClick={() => removeChapter(idx)} className="text-xs" style={{ color: "var(--accent-mark)" }}>
                  Remove
                </button>
              </div>
            ))}
            <button type="button" onClick={addChapter} className="text-xs font-semibold" style={{ color: "var(--accent)" }}>
              + Add a chapter
            </button>
          </div>
        </div>
      )}

      {draft.document_type === "blueprint" && (
        <>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              Topics &amp; marks
            </p>
            <div className="mt-1.5 space-y-1.5">
              {draft.topics.map((t, idx) => (
                <div key={idx} className="flex flex-wrap items-center gap-1.5">
                  <input
                    type="text"
                    value={t.topic_name}
                    onChange={(e) => updateTopic(idx, { topic_name: e.target.value })}
                    placeholder="Topic name"
                    className="flex-1 rounded-md border px-2 py-1 text-xs"
                    style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
                  />
                  <input
                    type="number"
                    value={t.marks}
                    onChange={(e) => updateTopic(idx, { marks: Number(e.target.value) })}
                    placeholder="Marks"
                    className="w-20 rounded-md border px-2 py-1 text-xs"
                    style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
                  />
                  <button type="button" onClick={() => removeTopic(idx)} className="text-xs" style={{ color: "var(--accent-mark)" }}>
                    Remove
                  </button>
                </div>
              ))}
              <button type="button" onClick={addTopic} className="text-xs font-semibold" style={{ color: "var(--accent)" }}>
                + Add a topic
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Exam format
            </label>
            <input
              type="text"
              value={draft.exam_format ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, exam_format: e.target.value }))}
              placeholder="e.g. 100 marks, 3 hours, 11 questions"
            />
          </div>
          <div>
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Tips (one per line)
            </label>
            <textarea
              value={draft.tips.join("\n")}
              onChange={(e) => setDraft((d) => ({ ...d, tips: e.target.value.split("\n").map((t) => t.trim()).filter(Boolean) }))}
              rows={3}
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
              style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
            />
          </div>
        </>
      )}

      {error && (
        <p className="text-xs" style={{ color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={saveDraft}
          disabled={saving}
          className="rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-60"
          style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
        >
          {saving ? "Saving…" : "Save edits"}
        </button>
        <button
          type="button"
          onClick={() => confirm()}
          disabled={confirming}
          className="accent-fill rounded-md px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
        >
          {confirming ? "Working…" : "Confirm & use"}
        </button>
        <button
          type="button"
          onClick={reject}
          disabled={confirming}
          className="rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-60"
          style={{ borderColor: "var(--border)", color: "var(--accent-mark)" }}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
