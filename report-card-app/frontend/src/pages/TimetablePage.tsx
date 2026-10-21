import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { CheckIcon, PlusIcon, TrashIcon } from "../components/Icons";
import type { TtClass, TtClassSubject, TtSchoolConfig, TtSubject, TtTeacher } from "../types";

type Tab = "classes" | "subjects" | "teachers" | "assignments" | "schedule";

const TABS: { id: Tab; label: string }[] = [
  { id: "schedule", label: "Schedule" },
  { id: "classes", label: "Classes" },
  { id: "subjects", label: "Subjects" },
  { id: "teachers", label: "Teachers" },
  { id: "assignments", label: "Assignments" },
];

const ALL_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
const DAY_LABEL: Record<string, string> = { MON: "Mon", TUE: "Tue", WED: "Wed", THU: "Thu", FRI: "Fri", SAT: "Sat", SUN: "Sun" };

function Panel({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="soft-card p-5">
      <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
        {title}
      </h2>
      {hint && (
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          {hint}
        </p>
      )}
      <div className="mt-4">{children}</div>
    </div>
  );
}

function Row({ children, onDelete }: { children: React.ReactNode; onDelete: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <div className="min-w-0 flex-1">{children}</div>
      <button
        type="button"
        onClick={onDelete}
        title="Delete"
        className="flex h-8 w-8 flex-none items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-mark-soft)]"
        style={{ color: "var(--text-muted)" }}
      >
        <TrashIcon size={15} />
      </button>
    </div>
  );
}

function EmptyHint({ children }: { children: React.ReactNode }) {
  return (
    <p className="py-3 text-center text-sm" style={{ color: "var(--text-muted)" }}>
      {children}
    </p>
  );
}

function ClassesTab({ classes, onAdd, onDelete }: { classes: TtClass[]; onAdd: (grade: string, section: string) => Promise<void>; onDelete: (id: number) => void }) {
  const [grade, setGrade] = useState("");
  const [section, setSection] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!grade.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onAdd(grade.trim(), section.trim());
      setGrade("");
      setSection("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this class");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Classes" hint="Every grade and section this school has — e.g. grade 10, section A.">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="w-28">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Grade
          </label>
          <input type="text" value={grade} onChange={(e) => setGrade(e.target.value)} placeholder="e.g. 10" required />
        </div>
        <div className="w-28">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Section
          </label>
          <input type="text" value={section} onChange={(e) => setSection(e.target.value)} placeholder="e.g. A" />
        </div>
        <button type="submit" disabled={busy} className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          <PlusIcon size={14} />
          Add class
        </button>
      </form>
      {error && <p className="mt-2 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}

      <div className="mt-4 divide-y" style={{ borderColor: "var(--border)" }}>
        {classes.map((c) => (
          <Row key={c.id} onDelete={() => onDelete(c.id)}>
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              Grade {c.grade}
              {c.section ? ` · Section ${c.section}` : ""}
            </span>
          </Row>
        ))}
        {classes.length === 0 && <EmptyHint>No classes yet — add your first one above.</EmptyHint>}
      </div>
    </Panel>
  );
}

function SubjectsTab({ subjects, onAdd, onDelete }: { subjects: TtSubject[]; onAdd: (name: string, code: string) => Promise<void>; onDelete: (id: number) => void }) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onAdd(name.trim(), code.trim());
      setName("");
      setCode("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this subject");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Subjects" hint="Every subject taught anywhere in the school — you'll set how many periods/week each gets, per class, under Assignments.">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="w-44">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Subject name
          </label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Mathematics" required />
        </div>
        <div className="w-28">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Short code
          </label>
          <input type="text" value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. M" />
        </div>
        <button type="submit" disabled={busy} className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          <PlusIcon size={14} />
          Add subject
        </button>
      </form>
      {error && <p className="mt-2 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}

      <div className="mt-4 divide-y" style={{ borderColor: "var(--border)" }}>
        {subjects.map((s) => (
          <Row key={s.id} onDelete={() => onDelete(s.id)}>
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              {s.name}
              {s.code && <span className="pill ml-2">{s.code}</span>}
            </span>
          </Row>
        ))}
        {subjects.length === 0 && <EmptyHint>No subjects yet — add your first one above.</EmptyHint>}
      </div>
    </Panel>
  );
}

function TeachersTab({ teachers, onAdd, onDelete }: { teachers: TtTeacher[]; onAdd: (name: string, code: string, maxPeriodsPerDay: number | null) => Promise<void>; onDelete: (id: number) => void }) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [maxPeriods, setMaxPeriods] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onAdd(name.trim(), code.trim(), maxPeriods.trim() ? Number(maxPeriods) : null);
      setName("");
      setCode("");
      setMaxPeriods("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this teacher");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Teachers" hint="Every teacher on staff. You'll assign which subject(s) and class(es) each one teaches under Assignments.">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="w-52">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Teacher name
          </label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. V.J.V. Shobhakar" required />
        </div>
        <div className="w-24">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Short code
          </label>
          <input type="text" value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. VJVS" />
        </div>
        <div className="w-36">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Max periods/day
          </label>
          <input type="number" min={1} max={12} value={maxPeriods} onChange={(e) => setMaxPeriods(e.target.value)} placeholder="Optional" />
        </div>
        <button type="submit" disabled={busy} className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          <PlusIcon size={14} />
          Add teacher
        </button>
      </form>
      {error && <p className="mt-2 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}

      <div className="mt-4 divide-y" style={{ borderColor: "var(--border)" }}>
        {teachers.map((t) => (
          <Row key={t.id} onDelete={() => onDelete(t.id)}>
            <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              {t.name}
              {t.code && <span className="pill ml-2">{t.code}</span>}
              {t.max_periods_per_day && (
                <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>
                  max {t.max_periods_per_day}/day
                </span>
              )}
            </span>
          </Row>
        ))}
        {teachers.length === 0 && <EmptyHint>No teachers yet — add your first one above.</EmptyHint>}
      </div>
    </Panel>
  );
}

function AssignmentsTab({ classes, subjects, teachers }: { classes: TtClass[]; subjects: TtSubject[]; teachers: TtTeacher[] }) {
  const [classId, setClassId] = useState<number | null>(classes[0]?.id ?? null);
  const [rows, setRows] = useState<TtClassSubject[] | null>(null);
  const [addSubjectId, setAddSubjectId] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);

  // Each row's edits are held in `drafts` and only sent as one combined PUT
  // when the row is saved — two separate requests (one per field) can land
  // out of order and silently drop whichever one's edit arrived first.
  const [drafts, setDrafts] = useState<Record<number, { teacherId: number | null; periodsPerWeek: number }>>({});

  useEffect(() => {
    setDrafts({});
    if (classId === null) {
      setRows(null);
      return;
    }
    setRows(null);
    api
      .get<TtClassSubject[]>(`/timetable/classes/${classId}/subjects`)
      .then(setRows)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load this class's subjects"));
  }, [classId]);

  function draftFor(r: TtClassSubject) {
    return drafts[r.subject_id] ?? { teacherId: r.teacher_id, periodsPerWeek: r.periods_per_week };
  }

  function editDraft(subjectId: number, patch: Partial<{ teacherId: number | null; periodsPerWeek: number }>, base: { teacherId: number | null; periodsPerWeek: number }) {
    setDrafts((prev) => ({ ...prev, [subjectId]: { ...base, ...patch } }));
  }

  async function saveRow(subjectId: number) {
    if (classId === null) return;
    const draft = drafts[subjectId];
    if (!draft) return;
    setError(null);
    try {
      const updated = await api.put<TtClassSubject>(`/timetable/classes/${classId}/subjects`, {
        subject_id: subjectId,
        teacher_id: draft.teacherId,
        periods_per_week: draft.periodsPerWeek,
      });
      setRows((prev) => (prev ? prev.map((r) => (r.subject_id === subjectId ? updated : r)) : prev));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[subjectId];
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this row");
    }
  }

  async function addSubject() {
    if (classId === null || addSubjectId === "") return;
    setError(null);
    try {
      const created = await api.put<TtClassSubject>(`/timetable/classes/${classId}/subjects`, {
        subject_id: addSubjectId,
        teacher_id: null,
        periods_per_week: 0,
      });
      setRows((prev) => (prev ? [...prev, created] : [created]));
      setAddSubjectId("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this subject to the class");
    }
  }

  async function removeSubject(subjectId: number) {
    if (classId === null) return;
    await api.del(`/timetable/classes/${classId}/subjects/${subjectId}`);
    setRows((prev) => (prev ? prev.filter((r) => r.subject_id !== subjectId) : prev));
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[subjectId];
      return next;
    });
  }

  if (classes.length === 0) {
    return (
      <Panel title="Assignments">
        <EmptyHint>Add at least one class under the Classes tab first.</EmptyHint>
      </Panel>
    );
  }
  if (subjects.length === 0 || teachers.length === 0) {
    return (
      <Panel title="Assignments">
        <EmptyHint>Add your subjects and teachers first, then come back here to assign them to each class.</EmptyHint>
      </Panel>
    );
  }

  const availableSubjects = subjects.filter((s) => !rows?.some((r) => r.subject_id === s.id));

  return (
    <Panel title="Assignments" hint="For each class: which subjects it has, how many periods/week, and who teaches it. Click the checkmark to save a row after editing it.">
      <div className="w-56">
        <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Class
        </label>
        <select
          value={classId ?? ""}
          onChange={(e) => setClassId(Number(e.target.value))}
          className="w-full rounded-md border px-3 py-2 text-sm font-medium"
          style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
        >
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              Grade {c.grade}
              {c.section ? ` · ${c.section}` : ""}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="mt-2 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}

      {rows && (
        <div className="mt-4 divide-y" style={{ borderColor: "var(--border)" }}>
          {rows.map((r) => {
            const draft = draftFor(r);
            const dirty = Boolean(drafts[r.subject_id]);
            return (
              <div key={r.subject_id} className="flex flex-wrap items-center gap-3 py-2.5">
                <span className="w-36 flex-none text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {r.subject_name}
                </span>
                <select
                  value={draft.teacherId ?? ""}
                  onChange={(e) => editDraft(r.subject_id, { teacherId: e.target.value ? Number(e.target.value) : null }, draft)}
                  className="min-w-0 flex-1 rounded-md border px-2.5 py-1.5 text-sm"
                  style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
                >
                  <option value="">— unassigned —</option>
                  {teachers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                      {t.code ? ` (${t.code})` : ""}
                    </option>
                  ))}
                </select>
                <div className="flex items-center gap-1.5">
                  <input
                    type="number"
                    min={0}
                    max={60}
                    value={draft.periodsPerWeek}
                    onChange={(e) => editDraft(r.subject_id, { periodsPerWeek: Number(e.target.value) || 0 }, draft)}
                    className="w-16 text-center"
                  />
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    /week
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => saveRow(r.subject_id)}
                  disabled={!dirty}
                  title="Save this row"
                  className="flex h-8 w-8 flex-none items-center justify-center rounded-full transition-colors duration-200 disabled:opacity-30"
                  style={{ color: dirty ? "var(--status-good)" : "var(--text-muted)" }}
                >
                  <CheckIcon size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => removeSubject(r.subject_id)}
                  title="Remove this subject from the class"
                  className="flex h-8 w-8 flex-none items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-mark-soft)]"
                  style={{ color: "var(--text-muted)" }}
                >
                  <TrashIcon size={15} />
                </button>
              </div>
            );
          })}
          {rows.length === 0 && <EmptyHint>No subjects assigned to this class yet.</EmptyHint>}
        </div>
      )}

      {availableSubjects.length > 0 && (
        <div className="mt-4 flex items-end gap-2 border-t pt-4" style={{ borderColor: "var(--border)" }}>
          <div className="w-52">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Add a subject to this class
            </label>
            <select
              value={addSubjectId}
              onChange={(e) => setAddSubjectId(e.target.value ? Number(e.target.value) : "")}
              className="w-full rounded-md border px-3 py-2 text-sm font-medium"
              style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
            >
              <option value="">Choose a subject…</option>
              {availableSubjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={addSubject}
            disabled={addSubjectId === ""}
            className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            <PlusIcon size={14} />
            Add
          </button>
        </div>
      )}
    </Panel>
  );
}

function ScheduleTab({ config, onSave }: { config: TtSchoolConfig; onSave: (config: TtSchoolConfig) => Promise<void> }) {
  const [days, setDays] = useState<Set<string>>(new Set(config.working_days));
  const [periodsPerDay, setPeriodsPerDay] = useState(String(config.periods_per_day));
  const [startTime, setStartTime] = useState(config.start_time);
  const [endTime, setEndTime] = useState(config.end_time);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function toggleDay(day: string) {
    setDays((prev) => {
      const next = new Set(prev);
      if (next.has(day)) next.delete(day);
      else next.add(day);
      return next;
    });
    setSaved(false);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSave({
        working_days: ALL_DAYS.filter((d) => days.has(d)),
        periods_per_day: Number(periodsPerDay) || 1,
        start_time: startTime,
        end_time: endTime,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the schedule");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Weekly schedule" hint="Start with this — the school day's shape. Which days run classes, what time the day starts and ends, and how many periods fit in it.">
      <form onSubmit={submit}>
        <div>
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Working days
          </label>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {ALL_DAYS.map((day) => {
              const active = days.has(day);
              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => toggleDay(day)}
                  className="rounded-full border px-3 py-1.5 text-sm font-medium transition-colors duration-200"
                  style={
                    active
                      ? { background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" }
                      : { borderColor: "var(--border)", color: "var(--text-secondary)" }
                  }
                >
                  {DAY_LABEL[day]}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-3">
          <div className="w-36">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              School starts
            </label>
            <input
              type="time"
              value={startTime}
              onChange={(e) => {
                setStartTime(e.target.value);
                setSaved(false);
              }}
              required
            />
          </div>
          <div className="w-36">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              School ends
            </label>
            <input
              type="time"
              value={endTime}
              onChange={(e) => {
                setEndTime(e.target.value);
                setSaved(false);
              }}
              required
            />
          </div>
          <div className="w-36">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Periods per day
            </label>
            <input
              type="number"
              min={1}
              max={12}
              value={periodsPerDay}
              onChange={(e) => {
                setPeriodsPerDay(e.target.value);
                setSaved(false);
              }}
              required
            />
          </div>
        </div>

        {error && <p className="mt-3 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}
        {saved && !error && <p className="mt-3 text-xs" style={{ color: "var(--status-good)" }}>Saved.</p>}

        <button type="submit" disabled={busy} className="accent-fill mt-4 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          {busy ? "Saving…" : "Save schedule"}
        </button>
      </form>
    </Panel>
  );
}

export function TimetablePage() {
  const [tab, setTab] = useState<Tab>("schedule");
  const [classes, setClasses] = useState<TtClass[] | null>(null);
  const [subjects, setSubjects] = useState<TtSubject[] | null>(null);
  const [teachers, setTeachers] = useState<TtTeacher[] | null>(null);
  const [config, setConfig] = useState<TtSchoolConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.get<TtClass[]>("/timetable/classes"),
      api.get<TtSubject[]>("/timetable/subjects"),
      api.get<TtTeacher[]>("/timetable/teachers"),
      api.get<TtSchoolConfig>("/timetable/config"),
    ])
      .then(([c, s, t, cfg]) => {
        setClasses(c);
        setSubjects(s);
        setTeachers(t);
        setConfig(cfg);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load the timetable setup"));
  }, []);

  async function addClass(grade: string, section: string) {
    const created = await api.post<TtClass>("/timetable/classes", { grade, section });
    setClasses((prev) => [...(prev ?? []), created]);
  }

  async function deleteClass(id: number) {
    await api.del(`/timetable/classes/${id}`);
    setClasses((prev) => prev?.filter((c) => c.id !== id) ?? prev);
  }

  async function addSubject(name: string, code: string) {
    const created = await api.post<TtSubject>("/timetable/subjects", { name, code });
    setSubjects((prev) => [...(prev ?? []), created]);
  }

  async function deleteSubject(id: number) {
    await api.del(`/timetable/subjects/${id}`);
    setSubjects((prev) => prev?.filter((s) => s.id !== id) ?? prev);
  }

  async function addTeacher(name: string, code: string, maxPeriodsPerDay: number | null) {
    const created = await api.post<TtTeacher>("/timetable/teachers", { name, code, max_periods_per_day: maxPeriodsPerDay });
    setTeachers((prev) => [...(prev ?? []), created]);
  }

  async function deleteTeacher(id: number) {
    await api.del(`/timetable/teachers/${id}`);
    setTeachers((prev) => prev?.filter((t) => t.id !== id) ?? prev);
  }

  async function saveConfig(next: TtSchoolConfig) {
    const updated = await api.put<TtSchoolConfig>("/timetable/config", next);
    setConfig(updated);
  }

  const loaded = classes && subjects && teachers && config;

  return (
    <section>
      <nav className="text-xs" style={{ color: "var(--text-muted)" }} aria-label="Breadcrumb">
        <Link to="/tools" className="hover:underline" style={{ color: "var(--text-muted)" }}>
          Tools
        </Link>{" "}
        / Timetable Creator
      </nav>
      <header className="mt-1">
        <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          Timetable Creator
        </h1>
        <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-secondary)" }}>
          Set up your classes, subjects, and teachers here. Once this is in place, the automatic weekly timetable
          generator and substitute-teacher assignment will build on exactly this data.
        </p>
      </header>

      {error && <p className="mt-4 text-sm" style={{ color: "var(--accent-mark)" }}>{error}</p>}

      <div className="mt-5 flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className="rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors duration-200"
            style={
              tab === t.id
                ? { background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" }
                : { borderColor: "var(--border)", color: "var(--text-secondary)" }
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {!loaded && <p className="text-sm" style={{ color: "var(--text-muted)" }}>Loading…</p>}
        {loaded && tab === "classes" && <ClassesTab classes={classes} onAdd={addClass} onDelete={deleteClass} />}
        {loaded && tab === "subjects" && <SubjectsTab subjects={subjects} onAdd={addSubject} onDelete={deleteSubject} />}
        {loaded && tab === "teachers" && <TeachersTab teachers={teachers} onAdd={addTeacher} onDelete={deleteTeacher} />}
        {loaded && tab === "assignments" && <AssignmentsTab classes={classes} subjects={subjects} teachers={teachers} />}
        {loaded && tab === "schedule" && <ScheduleTab config={config} onSave={saveConfig} />}
      </div>
    </section>
  );
}
