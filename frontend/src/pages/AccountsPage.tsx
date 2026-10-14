import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useClasses } from "../context/ClassesContext";
import type { AccountsResponse, Meta, SchoolClass, TeacherAccount, TeacherAssignment } from "../types";

function titleCase(s: string): string {
  return s.charAt(0) + s.slice(1).toLowerCase();
}

/** Within one already-chosen class: pick sections, then for each chosen
 * section pick its subjects and whether the teacher is limited to just
 * those subjects there. */
function ClassSectionPicker({
  classId,
  value,
  onChange,
}: {
  classId: number;
  value: TeacherAssignment[];
  onChange: (next: TeacherAssignment[]) => void;
}) {
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    setMeta(null);
    api.get<Meta>(`/meta?class_id=${classId}`).then(setMeta).catch(() => {});
  }, [classId]);

  function toggleSection(section: string) {
    if (value.some((a) => a.section === section)) {
      onChange(value.filter((a) => a.section !== section));
    } else {
      onChange([...value, { class_id: classId, section, subjects: [], restricted: false }]);
    }
  }

  function patch(section: string, next: Partial<TeacherAssignment>) {
    onChange(value.map((a) => (a.section === section ? { ...a, ...next } : a)));
  }

  function toggleSubject(section: string, subject: string) {
    const a = value.find((x) => x.section === section);
    if (!a) return;
    const nextSubjects = a.subjects.includes(subject) ? a.subjects.filter((s) => s !== subject) : [...a.subjects, subject];
    patch(section, { subjects: nextSubjects });
  }

  if (!meta) return <p className="text-xs" style={{ color: "var(--text-muted)" }}>Loading sections…</p>;

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {meta.sections.map((s) => {
          const active = value.some((a) => a.section === s);
          return (
            <button
              key={s}
              type="button"
              onClick={() => toggleSection(s)}
              className="rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors"
              style={{
                borderColor: "var(--border)",
                color: active ? "var(--accent)" : "var(--text-secondary)",
                background: active ? "var(--accent-soft)" : "transparent",
              }}
            >
              Section {s}
            </button>
          );
        })}
        {meta.sections.length === 0 && (
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>Upload a workbook to this class first.</span>
        )}
      </div>

      {value.length > 0 && (
        <div className="mt-3 space-y-3">
          {value.map((a) => (
            <div key={a.section} className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
              <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                Section {a.section} — subjects
              </div>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {meta.subjects.map((subj) => {
                  const picked = a.subjects.includes(subj);
                  return (
                    <button
                      key={subj}
                      type="button"
                      onClick={() => toggleSubject(a.section, subj)}
                      className="rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
                      style={{
                        borderColor: "var(--border)",
                        color: picked ? "var(--accent)" : "var(--text-secondary)",
                        background: picked ? "var(--accent-soft)" : "transparent",
                      }}
                    >
                      {titleCase(subj)}
                    </button>
                  );
                })}
              </div>
              <label className="mt-2 flex items-center gap-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                <input
                  type="checkbox"
                  checked={a.restricted}
                  onChange={(e) => patch(a.section, { restricted: e.target.checked })}
                />
                Restrict to only the selected subject(s) in Section {a.section} — otherwise sees every subject here
              </label>
              {a.restricted && a.subjects.length === 0 && (
                <p className="mt-1 text-xs" style={{ color: "var(--accent-mark)" }}>
                  Pick at least one subject, or turn restriction off.
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** A teacher's full assignment set can span several classes — e.g.
 * restricted to Maths in Class 9's Section A, and full access to Class
 * 10's Section B. Each class gets its own block, added one at a time. */
function AssignmentEditor({
  value,
  onChange,
}: {
  value: TeacherAssignment[];
  onChange: (next: TeacherAssignment[]) => void;
}) {
  const { classes } = useClasses();
  const [activeClassIds, setActiveClassIds] = useState<number[]>(() => Array.from(new Set(value.map((a) => a.class_id))));
  const [pickValue, setPickValue] = useState("");

  const availableClasses = classes.filter((c) => !activeClassIds.includes(c.id));

  function addClass() {
    const id = Number(pickValue);
    if (!id) return;
    setActiveClassIds((prev) => [...prev, id]);
    setPickValue("");
  }

  function removeClass(classId: number) {
    setActiveClassIds((prev) => prev.filter((id) => id !== classId));
    onChange(value.filter((a) => a.class_id !== classId));
  }

  function setClassAssignments(classId: number, next: TeacherAssignment[]) {
    onChange([...value.filter((a) => a.class_id !== classId), ...next]);
  }

  return (
    <div className="space-y-3">
      {activeClassIds.map((classId) => {
        const cls = classes.find((c) => c.id === classId);
        return (
          <div key={classId} className="rounded-xl border p-3" style={{ borderColor: "var(--border)" }}>
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                {cls?.name ?? `Class ${classId}`}
              </div>
              <button
                type="button"
                onClick={() => removeClass(classId)}
                className="text-xs font-medium"
                style={{ color: "var(--accent-mark)" }}
              >
                Remove class
              </button>
            </div>
            <div className="mt-2">
              <ClassSectionPicker
                classId={classId}
                value={value.filter((a) => a.class_id === classId)}
                onChange={(next) => setClassAssignments(classId, next)}
              />
            </div>
          </div>
        );
      })}

      {availableClasses.length > 0 && (
        <div className="flex items-center gap-2">
          <select
            value={pickValue}
            onChange={(e) => setPickValue(e.target.value)}
            className="flex-1 rounded-xl border px-3 py-2 text-sm"
            style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
          >
            <option value="">Add a class…</option>
            {availableClasses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={addClass}
            disabled={!pickValue}
            className="rounded-full border px-4 py-2 text-sm font-medium disabled:opacity-50"
            style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
          >
            Add
          </button>
        </div>
      )}
    </div>
  );
}

function assignmentsInvalid(assignments: TeacherAssignment[]): boolean {
  return assignments.length === 0 || assignments.some((a) => a.restricted && a.subjects.length === 0);
}

function assignmentSummary(a: TeacherAssignment, classes: SchoolClass[]): string {
  const className = classes.find((c) => c.id === a.class_id)?.name ?? `Class ${a.class_id}`;
  if (!a.restricted || a.subjects.length === 0) return `${className} — Section ${a.section}: all subjects`;
  return `${className} — Section ${a.section}: ${a.subjects.map(titleCase).join(", ")} only`;
}

export function AccountsPage() {
  const { user } = useAuth();
  const { classes } = useClasses();
  const [accounts, setAccounts] = useState<AccountsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [assignments, setAssignments] = useState<TeacherAssignment[]>([]);
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<TeacherAssignment[]>([]);
  const [savingEdit, setSavingEdit] = useState(false);

  function reload() {
    api.get<AccountsResponse>("/accounts").then(setAccounts).catch((e) => setError(e.message));
  }

  useEffect(() => {
    reload();
  }, []);

  async function createTeacher(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setCreating(true);
    try {
      await api.post<TeacherAccount>("/accounts/teachers", { email, password, display_name: displayName, assignments });
      setEmail("");
      setPassword("");
      setDisplayName("");
      setAssignments([]);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create teacher login");
    } finally {
      setCreating(false);
    }
  }

  function startEdit(t: TeacherAccount) {
    setEditingId(t.id);
    setEditDraft(t.assignments.map((a) => ({ ...a, subjects: [...a.subjects] })));
  }

  async function saveEdit(id: number) {
    setSavingEdit(true);
    try {
      await api.put(`/accounts/teachers/${id}/assignments`, { assignments: editDraft });
      setEditingId(null);
      reload();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Could not save changes");
    } finally {
      setSavingEdit(false);
    }
  }

  async function removeTeacher(id: number) {
    if (!confirm("Remove this teacher login?")) return;
    await api.del(`/accounts/teachers/${id}`);
    reload();
  }

  async function removeStudentLogin(id: number) {
    if (!confirm("Remove this student login?")) return;
    await api.del(`/accounts/students/${id}`);
    reload();
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          Accounts
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Create teacher logins and manage student roll-number logins. A teacher can be assigned to sections across
          several classes, and for each section choose whether they see every subject there or only specific ones.
          Your school code is{" "}
          <strong className="font-mono" style={{ color: "var(--text-primary)" }}>
            {user?.school_code}
          </strong>{" "}
          — students need it to sign in.
        </p>
      </div>

      <section>
        <h2 className="section-bar text-base font-medium">Add a teacher</h2>
        <form onSubmit={createTeacher} className="soft-card mt-2 space-y-4 p-6">
          <label className="block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Name</span>
            <input
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
          <label className="block">
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Password (min 8 characters)</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1.5 block w-full rounded-xl border px-4 py-2.5 text-sm"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
            />
          </label>
          <div>
            <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>Classes, sections and subjects they teach</span>
            <div className="mt-1.5">
              <AssignmentEditor value={assignments} onChange={setAssignments} />
            </div>
          </div>

          {error && (
            <p className="rounded-xl p-2.5 text-xs" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={creating || assignmentsInvalid(assignments)}
            className="gradient-fill rounded-full px-5 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-50"
          >
            Create teacher login
          </button>
        </form>
      </section>

      <section>
        <h2 className="section-bar text-base font-medium">Teachers</h2>
        <div className="soft-card mt-2 divide-y" style={{ borderColor: "var(--border)" }}>
          {accounts?.teachers.map((t) => (
            <div key={t.id} className="px-4 py-3">
              {editingId === t.id ? (
                <div className="space-y-3">
                  <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{t.display_name}</div>
                  <AssignmentEditor value={editDraft} onChange={setEditDraft} />
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveEdit(t.id)}
                      disabled={savingEdit || assignmentsInvalid(editDraft)}
                      className="gradient-fill rounded-full px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="rounded-full border px-4 py-1.5 text-xs font-medium"
                      style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{t.display_name}</div>
                    <div className="text-xs" style={{ color: "var(--text-muted)" }}>{t.email}</div>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {t.assignments.map((a) => (
                        <span
                          key={`${a.class_id}-${a.section}`}
                          className="rounded-full px-2.5 py-0.5 text-xs"
                          style={{ background: "var(--accent-soft)", color: "var(--text-secondary)" }}
                        >
                          {assignmentSummary(a, classes)}
                        </span>
                      ))}
                      {t.assignments.length === 0 && (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>No sections assigned</span>
                      )}
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      onClick={() => startEdit(t)}
                      className="rounded-full border px-3 py-1.5 text-xs font-medium"
                      style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => removeTeacher(t.id)}
                      className="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--accent-mark-soft)]"
                      style={{ borderColor: "var(--border)", color: "var(--accent-mark)" }}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {accounts && accounts.teachers.length === 0 && (
            <p className="p-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>No teacher logins yet.</p>
          )}
        </div>
      </section>

      <section>
        <h2 className="section-bar text-base font-medium">Student logins</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
          Create a student's login from their own page (open a student under a class's Students list, then "Create
          login").
        </p>
        <div className="soft-card mt-2 divide-y" style={{ borderColor: "var(--border)" }}>
          {accounts?.students.map((s) => (
            <div key={s.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div>
                <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{s.display_name}</div>
                <div className="font-mono text-xs" style={{ color: "var(--text-muted)" }}>
                  Roll {s.roll_no} · {classes.find((c) => c.id === s.class_id)?.name ?? `Class ${s.class_id}`} · Section {s.section}
                </div>
              </div>
              <button
                onClick={() => removeStudentLogin(s.id)}
                className="rounded-full border px-3 py-1.5 text-xs font-medium transition-colors hover:bg-[var(--accent-mark-soft)]"
                style={{ borderColor: "var(--border)", color: "var(--accent-mark)" }}
              >
                Remove
              </button>
            </div>
          ))}
          {accounts && accounts.students.length === 0 && (
            <p className="p-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>No student logins yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
