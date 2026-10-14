import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useClasses } from "../context/ClassesContext";
import type { SchoolClass } from "../types";

export function ManageClassesPage() {
  const { classes, loading, reload } = useClasses();
  const [name, setName] = useState("");
  const [shortCode, setShortCode] = useState("");
  const [sectionCount, setSectionCount] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [sectionError, setSectionError] = useState<Record<number, string>>({});

  async function createClass(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setCreating(true);
    try {
      await api.post<SchoolClass>("/school-classes", { name, short_code: shortCode, section_count: sectionCount });
      setName("");
      setShortCode("");
      setSectionCount(1);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create class");
    } finally {
      setCreating(false);
    }
  }

  function startEdit(c: SchoolClass) {
    setEditingId(c.id);
    setEditName(c.name);
  }

  async function saveEdit(id: number) {
    await api.put(`/school-classes/${id}`, { name: editName });
    setEditingId(null);
    reload();
  }

  async function updateSectionCount(id: number, count: number) {
    setSectionError((prev) => ({ ...prev, [id]: "" }));
    try {
      await api.put(`/school-classes/${id}/sections`, { section_count: count });
      reload();
    } catch (err) {
      setSectionError((prev) => ({ ...prev, [id]: err instanceof Error ? err.message : "Could not update sections" }));
    }
  }

  async function removeClass(c: SchoolClass) {
    if (!confirm(`Delete "${c.name}"?`)) return;
    try {
      await api.del(`/school-classes/${c.id}`);
      reload();
      return;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Could not delete class";
      if (!message.toLowerCase().includes("still has students")) {
        alert(message);
        return;
      }
      // Blocked because it has data — offer a force-delete, gated behind
      // typing the class name back (like GitHub's repo deletion), since
      // this permanently wipes every student, mark, attendance record,
      // textbook and student login in the class with no undo.
      const typed = prompt(
        `"${c.name}" still has students and data in it. Deleting it anyway will PERMANENTLY remove all of its students, marks, attendance, textbooks, and any student logins — this cannot be undone.\n\nType the class name exactly to confirm: ${c.name}`,
      );
      if (typed === null) return;
      if (typed !== c.name) {
        alert("That didn't match the class name — nothing was deleted.");
        return;
      }
      try {
        await api.del(`/school-classes/${c.id}?force=true`);
        reload();
      } catch (err2) {
        alert(err2 instanceof Error ? err2.message : "Could not delete class");
      }
    }
  }

  if (loading) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          Classes
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Each class (e.g. "Class 9", "Class 10") has its own upload, sections, students and textbooks. Create one for
          every grade you track here, then switch between them from the header.
        </p>
      </div>

      <form onSubmit={createClass} className="soft-card space-y-3 p-5">
        <label className="block">
          <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Class name</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Class 9"
            className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
            style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
            Short code (used in student roll numbers, e.g. "9")
          </span>
          <input
            required
            value={shortCode}
            onChange={(e) => setShortCode(e.target.value)}
            placeholder="9"
            className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm uppercase"
            style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
          />
        </label>
        <label className="block">
          <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
            Number of sections (e.g. A, B, C — you can add more later)
          </span>
          <input
            required
            type="number"
            min={1}
            max={26}
            value={sectionCount}
            onChange={(e) => setSectionCount(Math.max(1, Math.min(26, Number(e.target.value) || 1)))}
            className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
            style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
          />
        </label>
        {error && (
          <p className="rounded-xl p-2.5 text-xs" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={creating}
          className="gradient-fill rounded-full px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          Create class
        </button>
      </form>

      <div className="soft-card divide-y" style={{ borderColor: "var(--border)" }}>
        {classes.map((c) => (
          <div key={c.id} className="px-4 py-3">
            {editingId === c.id ? (
              <div className="flex items-center gap-3">
                <input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="flex-1 rounded-lg border px-2.5 py-1.5 text-sm"
                  style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => saveEdit(c.id)}
                    className="rounded-full border px-3 py-1.5 text-xs font-semibold"
                    style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
                  >
                    Save
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="rounded-full border px-3 py-1.5 text-xs font-medium"
                    style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{c.name}</div>
                  <div className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>{c.short_code ?? "—"}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    to={`/c/${c.id}/sections`}
                    className="rounded-full border px-3 py-1.5 text-xs font-medium"
                    style={{ borderColor: "var(--border)", color: "var(--accent)" }}
                  >
                    View students
                  </Link>
                  <button
                    onClick={() => startEdit(c)}
                    className="rounded-full border px-3 py-1.5 text-xs font-medium"
                    style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                  >
                    Rename
                  </button>
                  <button
                    onClick={() => removeClass(c)}
                    className="rounded-full border px-3 py-1.5 text-xs font-medium"
                    style={{ borderColor: "var(--border)", color: "var(--accent-mark)" }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            )}

            {editingId !== c.id && (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                <span>
                  Sections:{" "}
                  {c.sections.length > 0 ? c.sections.map((s) => `Section ${s}`).join(", ") : "none yet"}
                </span>
                <button
                  onClick={() => updateSectionCount(c.id, c.sections.length + 1)}
                  className="rounded-full border px-2.5 py-1 text-xs font-medium"
                  style={{ borderColor: "var(--border)", color: "var(--accent)" }}
                >
                  + Add section
                </button>
                {c.sections.length > 1 && (
                  <button
                    onClick={() => updateSectionCount(c.id, c.sections.length - 1)}
                    className="rounded-full border px-2.5 py-1 text-xs font-medium"
                    style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                  >
                    − Remove last section
                  </button>
                )}
                {sectionError[c.id] && <span style={{ color: "var(--accent-mark)" }}>{sectionError[c.id]}</span>}
              </div>
            )}
          </div>
        ))}
        {classes.length === 0 && (
          <p className="p-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>
            No classes yet — create your first one above.
          </p>
        )}
      </div>
    </div>
  );
}
