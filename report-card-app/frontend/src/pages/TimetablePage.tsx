import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { CheckIcon, PlusIcon, TrashIcon } from "../components/Icons";
import type {
  TtBreak,
  TtClass,
  TtClassSubject,
  TtGenerateResult,
  TtSchoolConfig,
  TtSubject,
  TtSubstituteCandidate,
  TtSubstituteOptions,
  TtSubstitution,
  TtTeacher,
  TtTeacherTimetableEntry,
  TtTimetableEntry,
} from "../types";

type Tab = "classes" | "subjects" | "teachers" | "assignments" | "schedule" | "timetable";

const TABS: { id: Tab; label: string }[] = [
  { id: "schedule", label: "Schedule" },
  { id: "classes", label: "Classes" },
  { id: "subjects", label: "Subjects" },
  { id: "teachers", label: "Teachers" },
  { id: "assignments", label: "Assignments" },
  { id: "timetable", label: "Timetable" },
];

const ALL_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
const DAY_LABEL: Record<string, string> = { MON: "Mon", TUE: "Tue", WED: "Wed", THU: "Thu", FRI: "Fri", SAT: "Sat", SUN: "Sun" };

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

function fromMinutes(total: number): string {
  const h = Math.floor(total / 60) % 24;
  const m = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function formatClock(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${String(m).padStart(2, "0")} ${period}`;
}

interface DayScheduleRow {
  kind: "period" | "break";
  label: string;
  start: string;
  end: string;
  period?: number; // set for kind: "period" rows — the 1-indexed period number
}

// Splits the school day into `periodsPerDay` equal(-ish) slots with each
// break inserted right after the period it follows — the same shape as
// every real timetable sheet we've seen (periods interleaved with short
// breaks and a lunch break), computed from the school's own start/end
// time rather than hand-entered per period.
function buildDaySchedule(startTime: string, endTime: string, periodsPerDay: number, breaks: TtBreak[]): DayScheduleRow[] | null {
  const totalMinutes = toMinutes(endTime) - toMinutes(startTime);
  const breakMinutes = breaks.reduce((sum, b) => sum + b.duration_minutes, 0);
  const teachingMinutes = totalMinutes - breakMinutes;
  if (periodsPerDay < 1 || teachingMinutes < periodsPerDay) return null;

  const base = Math.floor(teachingMinutes / periodsPerDay);
  const extra = teachingMinutes % periodsPerDay; // first `extra` periods run one minute longer, so the total matches exactly
  const breaksByAfter = new Map(breaks.map((b) => [b.after_period, b]));

  const rows: DayScheduleRow[] = [];
  let cursor = toMinutes(startTime);
  for (let i = 1; i <= periodsPerDay; i++) {
    const duration = base + (i <= extra ? 1 : 0);
    const start = cursor;
    cursor += duration;
    rows.push({ kind: "period", label: `Period ${i}`, start: fromMinutes(start), end: fromMinutes(cursor), period: i });
    const brk = breaksByAfter.get(i);
    if (brk) {
      const bStart = cursor;
      cursor += brk.duration_minutes;
      rows.push({ kind: "break", label: brk.label, start: fromMinutes(bStart), end: fromMinutes(cursor) });
    }
  }
  return rows;
}

// Shared by the blank Schedule-tab preview and the filled generated-timetable
// view — same Time + day-columns grid, just a different `renderCell`.
function WeekGrid({
  schedule,
  workingDays,
  renderCell,
}: {
  schedule: DayScheduleRow[];
  workingDays: string[];
  renderCell?: (day: string, period: number) => React.ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm" style={{ minWidth: 560 }}>
        <thead>
          <tr>
            <th
              className="whitespace-nowrap border px-3 py-2 text-left text-xs font-semibold"
              style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-secondary)" }}
            >
              Time
            </th>
            {workingDays.map((d) => (
              <th
                key={d}
                className="whitespace-nowrap border px-3 py-2 text-left text-xs font-semibold"
                style={{ borderColor: "var(--border)", background: "var(--accent)", color: "#fff" }}
              >
                {DAY_LABEL[d]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {schedule.map((row, i) =>
            row.kind === "break" ? (
              <tr key={i}>
                <td
                  colSpan={workingDays.length + 1}
                  className="border px-3 py-1.5 text-center text-xs italic"
                  style={{ borderColor: "var(--border)", background: "var(--accent-soft)", color: "var(--text-secondary)" }}
                >
                  {row.label} · {formatClock(row.start)} – {formatClock(row.end)}
                </td>
              </tr>
            ) : (
              <tr key={i}>
                <td className="whitespace-nowrap border px-3 py-2 align-top" style={{ borderColor: "var(--border)", background: "var(--page-plane)" }}>
                  <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                    {row.label}
                  </div>
                  <div className="tabular-nums text-xs" style={{ color: "var(--text-muted)" }}>
                    {formatClock(row.start)} – {formatClock(row.end)}
                  </div>
                </td>
                {workingDays.map((d) => (
                  <td key={d} className="border px-3 py-2 align-top" style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}>
                    {renderCell ? renderCell(d, row.period as number) : null}
                  </td>
                ))}
              </tr>
            )
          )}
        </tbody>
      </table>
    </div>
  );
}

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

function SubjectTogglePill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border px-2.5 py-1 text-xs font-medium transition-colors duration-200"
      style={active ? { background: "var(--accent)", borderColor: "var(--accent)", color: "#fff" } : { borderColor: "var(--border)", color: "var(--text-secondary)" }}
    >
      {label}
    </button>
  );
}

function TeacherTimetableModal({
  teacherId,
  teacherName,
  config,
  onClose,
}: {
  teacherId: number;
  teacherName: string;
  config: TtSchoolConfig;
  onClose: () => void;
}) {
  const [entries, setEntries] = useState<TtTeacherTimetableEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<TtTeacherTimetableEntry[]>(`/timetable/teachers/${teacherId}/timetable`)
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load this teacher's timetable"));
  }, [teacherId]);

  const schedule = buildDaySchedule(config.start_time, config.end_time, config.periods_per_day, config.breaks);
  const workingDays = ALL_DAYS.filter((d) => config.working_days.includes(d));
  const entryBySlot = new Map<string, TtTeacherTimetableEntry>();
  entries?.forEach((e) => entryBySlot.set(`${e.day}-${e.period}`, e));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(15,23,42,0.45)" }} onClick={onClose}>
      <div
        className="soft-card w-full max-w-3xl overflow-y-auto p-5"
        style={{ boxShadow: "var(--shadow-pop)", maxHeight: "90vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            {teacherName}'s timetable
          </h3>
          <button type="button" onClick={onClose} className="text-xl leading-none" style={{ color: "var(--text-muted)" }}>
            ×
          </button>
        </div>

        {error && <p className="mt-3 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}
        {!error && !schedule && (
          <p className="mt-3 text-sm" style={{ color: "var(--accent-mark)" }}>
            Set up a valid Schedule first before a teacher's timetable can be displayed.
          </p>
        )}
        {schedule && (
          <div className="mt-3">
            <WeekGrid
              schedule={schedule}
              workingDays={workingDays}
              renderCell={(day, period) => {
                const entry = entryBySlot.get(`${day}-${period}`);
                if (!entry) {
                  return entries === null ? null : (
                    <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                      Free
                    </span>
                  );
                }
                const [grade, section] = entry.class_name.split(" ");
                return (
                  <div>
                    <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                      Grade {grade}
                      {section ? ` · ${section}` : ""}
                    </div>
                    <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                      {entry.subject_name}
                    </div>
                  </div>
                );
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function TeachersTab({
  teachers,
  subjects,
  config,
  onAdd,
  onDelete,
  onUpdateSubjects,
}: {
  teachers: TtTeacher[];
  subjects: TtSubject[];
  config: TtSchoolConfig;
  onAdd: (name: string, code: string, maxPeriodsPerDay: number | null, subjectIds: number[]) => Promise<void>;
  onDelete: (id: number) => void;
  onUpdateSubjects: (teacherId: number, subjectIds: number[]) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [maxPeriods, setMaxPeriods] = useState("");
  const [newSubjectIds, setNewSubjectIds] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [subjectDrafts, setSubjectDrafts] = useState<Record<number, number[]>>({});
  const [viewingTeacher, setViewingTeacher] = useState<TtTeacher | null>(null);

  function subjectsFor(t: TtTeacher): number[] {
    return subjectDrafts[t.id] ?? t.subject_ids;
  }

  function toggleDraftSubject(t: TtTeacher, subjectId: number) {
    const current = subjectsFor(t);
    const next = current.includes(subjectId) ? current.filter((x) => x !== subjectId) : [...current, subjectId];
    setSubjectDrafts((prev) => ({ ...prev, [t.id]: next }));
  }

  async function saveSubjects(t: TtTeacher) {
    const ids = subjectDrafts[t.id];
    if (!ids) return;
    await onUpdateSubjects(t.id, ids);
    setSubjectDrafts((prev) => {
      const next = { ...prev };
      delete next[t.id];
      return next;
    });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onAdd(name.trim(), code.trim(), maxPeriods.trim() ? Number(maxPeriods) : null, newSubjectIds);
      setName("");
      setCode("");
      setMaxPeriods("");
      setNewSubjectIds([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this teacher");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Teachers" hint="Every teacher on staff, and which subject(s) they teach — used to suggest the right teacher under Assignments.">
      <form onSubmit={submit}>
        <div className="flex flex-wrap items-end gap-2">
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
        </div>

        {subjects.length > 0 && (
          <div className="mt-3">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Subjects they teach
            </label>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {subjects.map((s) => (
                <SubjectTogglePill
                  key={s.id}
                  label={s.name}
                  active={newSubjectIds.includes(s.id)}
                  onClick={() => setNewSubjectIds((prev) => (prev.includes(s.id) ? prev.filter((x) => x !== s.id) : [...prev, s.id]))}
                />
              ))}
            </div>
          </div>
        )}

        {error && <p className="mt-2 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}
      </form>

      <div className="mt-4 divide-y" style={{ borderColor: "var(--border)" }}>
        {teachers.map((t) => {
          const current = subjectsFor(t);
          const dirty = subjectDrafts[t.id] !== undefined;
          return (
            <Row key={t.id} onDelete={() => onDelete(t.id)}>
              <button
                type="button"
                onClick={() => setViewingTeacher(t)}
                title="View this teacher's own timetable"
                className="text-sm font-medium underline-offset-2 hover:underline"
                style={{ color: "var(--text-primary)" }}
              >
                {t.name}
                {t.code && <span className="pill ml-2">{t.code}</span>}
                {t.max_periods_per_day && (
                  <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>
                    max {t.max_periods_per_day}/day
                  </span>
                )}
              </button>
              {subjects.length > 0 && (
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {subjects.map((s) => (
                    <SubjectTogglePill key={s.id} label={s.name} active={current.includes(s.id)} onClick={() => toggleDraftSubject(t, s.id)} />
                  ))}
                  {dirty && (
                    <button
                      type="button"
                      onClick={() => saveSubjects(t)}
                      title="Save subjects"
                      className="flex h-6 w-6 flex-none items-center justify-center rounded-full"
                      style={{ color: "var(--status-good)" }}
                    >
                      <CheckIcon size={13} />
                    </button>
                  )}
                </div>
              )}
            </Row>
          );
        })}
        {teachers.length === 0 && <EmptyHint>No teachers yet — add your first one above.</EmptyHint>}
      </div>

      {viewingTeacher && (
        <TeacherTimetableModal
          teacherId={viewingTeacher.id}
          teacherName={viewingTeacher.name}
          config={config}
          onClose={() => setViewingTeacher(null)}
        />
      )}
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
            const matching = teachers.filter((t) => t.subject_ids.includes(r.subject_id));
            const others = teachers.filter((t) => !t.subject_ids.includes(r.subject_id));
            const teacherOption = (t: TtTeacher) => (
              <option key={t.id} value={t.id}>
                {t.name}
                {t.code ? ` (${t.code})` : ""}
              </option>
            );
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
                  {matching.length > 0 && others.length > 0 ? (
                    <>
                      <optgroup label={`Teaches ${r.subject_name}`}>{matching.map(teacherOption)}</optgroup>
                      <optgroup label="Other teachers">{others.map(teacherOption)}</optgroup>
                    </>
                  ) : (
                    teachers.map(teacherOption)
                  )}
                </select>
                <div className="flex items-center gap-1.5">
                  <input
                    type="number"
                    min={0}
                    max={60}
                    value={draft.periodsPerWeek}
                    onChange={(e) => editDraft(r.subject_id, { periodsPerWeek: Number(e.target.value) || 0 }, draft)}
                    className="text-center"
                    style={{ width: "4rem" }}
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

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function SubstituteModal({
  classId,
  day,
  period,
  onClose,
  onAssigned,
}: {
  classId: number;
  day: string;
  period: number;
  onClose: () => void;
  onAssigned: () => void;
}) {
  const [date, setDate] = useState(todayStr);
  const [options, setOptions] = useState<TtSubstituteOptions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [assigning, setAssigning] = useState<number | null>(null);
  const [assigned, setAssigned] = useState<string | null>(null);

  useEffect(() => {
    setOptions(null);
    setError(null);
    setAssigned(null);
    api
      .get<TtSubstituteOptions>(`/timetable/classes/${classId}/substitutes?day=${day}&period=${period}&date=${date}`)
      .then(setOptions)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load substitute options"));
  }, [classId, day, period, date]);

  async function assign(teacherId: number, teacherName: string) {
    setAssigning(teacherId);
    setError(null);
    try {
      await api.post(`/timetable/classes/${classId}/substitutions`, { date, day, period, substitute_teacher_id: teacherId });
      setAssigned(teacherName);
      onAssigned();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not assign this substitute");
    } finally {
      setAssigning(null);
    }
  }

  const groups: { key: TtSubstituteCandidate["reason"]; label: string }[] = [
    { key: "subject", label: "Teaches this subject" },
    { key: "class", label: "Already teaches this class" },
    { key: "other", label: "Other free teachers" },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(15,23,42,0.45)" }}
      onClick={onClose}
    >
      <div className="soft-card w-full max-w-md p-5" style={{ boxShadow: "var(--shadow-pop)" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
              {DAY_LABEL[day]}, Period {period}
            </h3>
            {options && (
              <p className="mt-0.5 text-sm" style={{ color: "var(--text-secondary)" }}>
                {options.original.subject_name} — {options.original.teacher_name ?? "unassigned"}
              </p>
            )}
          </div>
          <button type="button" onClick={onClose} className="text-xl leading-none" style={{ color: "var(--text-muted)" }}>
            ×
          </button>
        </div>

        <div className="mt-3 w-44">
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {options?.original.teacher_name ?? "Teacher"} is absent on
          </label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>

        {error && <p className="mt-3 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}
        {assigned && (
          <p className="mt-3 text-sm" style={{ color: "var(--status-good)" }}>
            Assigned {assigned} to cover this period.
          </p>
        )}

        <div className="mt-4 max-h-80 overflow-y-auto">
          {!options && !error && (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Loading…
            </p>
          )}
          {options &&
            groups.map((g) => {
              const list = options.candidates.filter((c) => c.reason === g.key);
              if (list.length === 0) return null;
              return (
                <div key={g.key} className="mt-3 first:mt-0">
                  <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                    {g.label}
                  </p>
                  <div className="mt-1.5 divide-y" style={{ borderColor: "var(--border)" }}>
                    {list.map((c) => (
                      <div key={c.teacher_id} className="flex items-center justify-between py-1.5">
                        <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                          {c.teacher_name}
                          {c.teacher_code && <span className="pill ml-2">{c.teacher_code}</span>}
                        </span>
                        <button
                          type="button"
                          onClick={() => assign(c.teacher_id, c.teacher_name)}
                          disabled={assigning !== null}
                          className="accent-fill rounded-md px-3 py-1 text-xs font-semibold text-white disabled:opacity-60"
                        >
                          {assigning === c.teacher_id ? "Assigning…" : "Assign"}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          {options && options.candidates.length === 0 && (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              No teacher is free at this period on this date.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function GeneratedTimetableTab({
  classes,
  config,
  onGenerate,
}: {
  classes: TtClass[];
  config: TtSchoolConfig;
  onGenerate: () => Promise<TtGenerateResult>;
}) {
  const [classId, setClassId] = useState<number | null>(classes[0]?.id ?? null);
  const [entries, setEntries] = useState<TtTimetableEntry[] | null>(null);
  const [todaySubs, setTodaySubs] = useState<TtSubstitution[]>([]);
  const [selectedCell, setSelectedCell] = useState<{ day: string; period: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TtGenerateResult | null>(null);

  const schedule = buildDaySchedule(config.start_time, config.end_time, config.periods_per_day, config.breaks);
  const workingDays = ALL_DAYS.filter((d) => config.working_days.includes(d));

  function refreshTodaySubs(id: number) {
    api
      .get<TtSubstitution[]>(`/timetable/classes/${id}/substitutions?date=${todayStr()}`)
      .then(setTodaySubs)
      .catch(() => setTodaySubs([]));
  }

  useEffect(() => {
    if (classId === null) {
      setEntries(null);
      setTodaySubs([]);
      return;
    }
    setEntries(null);
    api
      .get<TtTimetableEntry[]>(`/timetable/classes/${classId}/timetable`)
      .then(setEntries)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load this class's timetable"));
    refreshTodaySubs(classId);
  }, [classId]);

  async function runGenerate() {
    if (!confirm("Generate the timetable? This replaces any previously generated timetable for every class.")) return;
    setBusy(true);
    setError(null);
    try {
      const res = await onGenerate();
      // Wait for the grid to actually have the fresh entries before
      // announcing success, so the "Done" message and the filled-in grid
      // appear together instead of the message landing a moment early.
      const fresh = classId !== null ? await api.get<TtTimetableEntry[]>(`/timetable/classes/${classId}/timetable`) : null;
      if (fresh !== null) setEntries(fresh);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate the timetable");
    } finally {
      setBusy(false);
    }
  }

  if (classes.length === 0) {
    return (
      <Panel title="Timetable">
        <EmptyHint>Add at least one class, with subjects and teachers assigned, before generating a timetable.</EmptyHint>
      </Panel>
    );
  }

  const entryBySlot = new Map<string, TtTimetableEntry>();
  entries?.forEach((e) => entryBySlot.set(`${e.day}-${e.period}`, e));

  return (
    <Panel title="Timetable" hint="Generate the weekly timetable for every class from your Schedule, Classes, Subjects, Teachers, and Assignments.">
      <button
        type="button"
        onClick={runGenerate}
        disabled={busy}
        className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
      >
        {busy ? "Generating…" : "Generate timetable"}
      </button>

      {error && <p className="mt-3 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}

      {result && (
        <div className="mt-3 rounded-lg p-3 text-sm" style={{ background: result.ok ? "var(--status-good-soft)" : "var(--accent-mark-soft)" }}>
          <p style={{ color: result.ok ? "var(--status-good)" : "var(--accent-mark)" }}>
            {result.ok
              ? `Done — generated a full timetable for ${result.classes_generated} class${result.classes_generated === 1 ? "" : "es"} (${result.total_periods_placed} periods placed).`
              : `Placed ${result.total_periods_placed} periods across ${result.classes_generated} class${result.classes_generated === 1 ? "" : "es"}, but some couldn't be fully scheduled:`}
          </p>
          {result.issues.length > 0 && (
            <ul className="mt-1.5 list-disc space-y-1 pl-5">
              {result.issues.map((issue, i) => (
                <li key={i} style={{ color: "var(--text-secondary)" }}>
                  <strong>{issue.class_name}</strong> — {issue.subject_name}: {issue.reason}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="mt-4 w-56">
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

      {schedule ? (
        <div className="mt-4">
          <WeekGrid
            schedule={schedule}
            workingDays={workingDays}
            renderCell={(day, period) => {
              const entry = entryBySlot.get(`${day}-${period}`);
              if (!entry) {
                return entries === null ? null : (
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    —
                  </span>
                );
              }
              const sub = todaySubs.find((s) => s.day === day && s.period === period);
              return (
                <button
                  type="button"
                  onClick={() => setSelectedCell({ day, period })}
                  title="Click to find a substitute if this teacher is absent"
                  className="flex w-full flex-col items-start rounded-md text-left transition-colors duration-200 hover:bg-[var(--accent-soft)]"
                >
                  <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                    {entry.subject_name}
                  </div>
                  {sub ? (
                    <div className="text-xs" style={{ color: "var(--status-good)" }}>
                      Sub: {sub.substitute_teacher_name}
                    </div>
                  ) : (
                    entry.teacher_name && (
                      <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {entry.teacher_name}
                      </div>
                    )
                  )}
                </button>
              );
            }}
          />
        </div>
      ) : (
        <p className="mt-4 text-sm" style={{ color: "var(--accent-mark)" }}>
          Set up a valid Schedule first (the breaks need to fit in the school day) before the timetable can be displayed.
        </p>
      )}

      {selectedCell && classId !== null && (
        <SubstituteModal
          classId={classId}
          day={selectedCell.day}
          period={selectedCell.period}
          onClose={() => setSelectedCell(null)}
          onAssigned={() => refreshTodaySubs(classId)}
        />
      )}
    </Panel>
  );
}

function ScheduleTab({ config, onSave }: { config: TtSchoolConfig; onSave: (config: TtSchoolConfig) => Promise<void> }) {
  const [days, setDays] = useState<Set<string>>(new Set(config.working_days));
  const [periodsPerDay, setPeriodsPerDay] = useState(String(config.periods_per_day));
  const [startTime, setStartTime] = useState(config.start_time);
  const [endTime, setEndTime] = useState(config.end_time);
  const [breaks, setBreaks] = useState<TtBreak[]>(config.breaks);
  const [breakAfter, setBreakAfter] = useState<number | "">("");
  const [breakDuration, setBreakDuration] = useState("10");
  const [breakLabel, setBreakLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const periodsNum = Number(periodsPerDay) || 0;
  const usedPositions = new Set(breaks.map((b) => b.after_period));
  const availablePositions = Array.from({ length: Math.max(periodsNum - 1, 0) }, (_, i) => i + 1).filter((p) => !usedPositions.has(p));
  const schedule = buildDaySchedule(startTime, endTime, periodsNum, breaks);
  const strandedBreaks = breaks.filter((b) => b.after_period >= periodsNum);

  function toggleDay(day: string) {
    setDays((prev) => {
      const next = new Set(prev);
      if (next.has(day)) next.delete(day);
      else next.add(day);
      return next;
    });
    setSaved(false);
  }

  function addBreak() {
    if (breakAfter === "") return;
    // Not re-sorted by position — editing a row's "after period" below would
    // otherwise jump that row to a new spot in the list mid-edit.
    setBreaks((prev) => [...prev, { after_period: breakAfter, duration_minutes: Number(breakDuration) || 1, label: breakLabel.trim() || "Break" }]);
    setBreakAfter("");
    setBreakDuration("10");
    setBreakLabel("");
    setSaved(false);
  }

  function updateBreakAt(index: number, patch: Partial<TtBreak>) {
    setBreaks((prev) => prev.map((b, i) => (i === index ? { ...b, ...patch } : b)));
    setSaved(false);
  }

  function removeBreakAt(index: number) {
    setBreaks((prev) => prev.filter((_, i) => i !== index));
    setSaved(false);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSave({
        working_days: ALL_DAYS.filter((d) => days.has(d)),
        periods_per_day: periodsNum || 1,
        start_time: startTime,
        end_time: endTime,
        breaks,
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

        <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--border)" }}>
          <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
            Breaks (short breaks, lunch break)
          </label>
          <div className="mt-2 divide-y" style={{ borderColor: "var(--border)" }}>
            {breaks.map((b, i) => {
              const usedByOthers = new Set(breaks.filter((_, j) => j !== i).map((x) => x.after_period));
              const rowPositions = Array.from({ length: Math.max(periodsNum - 1, 0) }, (_, k) => k + 1).filter(
                (p) => p === b.after_period || !usedByOthers.has(p)
              );
              return (
                <div key={i} className="flex flex-wrap items-center gap-2 py-1.5">
                  <input
                    type="text"
                    value={b.label}
                    onChange={(e) => updateBreakAt(i, { label: e.target.value })}
                    className="min-w-0 flex-1"
                  />
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    after period
                  </span>
                  <select
                    value={b.after_period}
                    onChange={(e) => updateBreakAt(i, { after_period: Number(e.target.value) })}
                    className="w-20 rounded-md border px-2 py-1.5 text-sm"
                    style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
                  >
                    {rowPositions.map((p) => (
                      <option key={p} value={p}>
                        {p}
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min={1}
                    max={180}
                    value={b.duration_minutes}
                    onChange={(e) => updateBreakAt(i, { duration_minutes: Number(e.target.value) || 1 })}
                    className="text-center"
                    style={{ width: "4rem" }}
                  />
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    min
                  </span>
                  <button
                    type="button"
                    onClick={() => removeBreakAt(i)}
                    title="Remove this break"
                    className="flex h-7 w-7 flex-none items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-mark-soft)]"
                    style={{ color: "var(--text-muted)" }}
                  >
                    <TrashIcon size={14} />
                  </button>
                </div>
              );
            })}
            {breaks.length === 0 && (
              <p className="py-1.5 text-sm" style={{ color: "var(--text-muted)" }}>
                No breaks yet — periods will run back-to-back until you add one.
              </p>
            )}
          </div>

          {availablePositions.length > 0 ? (
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <div className="w-32">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  After period
                </label>
                <select
                  value={breakAfter}
                  onChange={(e) => setBreakAfter(e.target.value ? Number(e.target.value) : "")}
                  className="w-full rounded-md border px-3 py-2 text-sm font-medium"
                  style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
                >
                  <option value="">Choose…</option>
                  {availablePositions.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>
              <div className="w-28">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Minutes
                </label>
                <input type="number" min={1} max={180} value={breakDuration} onChange={(e) => setBreakDuration(e.target.value)} />
              </div>
              <div className="w-40">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Label
                </label>
                <input type="text" value={breakLabel} onChange={(e) => setBreakLabel(e.target.value)} placeholder="e.g. Lunch break" />
              </div>
              <button
                type="button"
                onClick={addBreak}
                disabled={breakAfter === ""}
                className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                <PlusIcon size={14} />
                Add break
              </button>
            </div>
          ) : (
            periodsNum > 1 && (
              <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                Every period already has a break assigned after it.
              </p>
            )
          )}
        </div>

        <div className="mt-5 border-t pt-4" style={{ borderColor: "var(--border)" }}>
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Weekly template
          </h3>
          <p className="mt-0.5 text-xs" style={{ color: "var(--text-secondary)" }}>
            This is the empty grid every class's timetable will follow — subjects and teachers fill it in once you've set up
            Classes, Subjects, Teachers, and Assignments.
          </p>
          {schedule ? (
            <div className="mt-3">
              <WeekGrid schedule={schedule} workingDays={ALL_DAYS.filter((d) => days.has(d))} />
            </div>
          ) : (
            <p className="mt-2 text-sm" style={{ color: "var(--accent-mark)" }}>
              The breaks below don't leave enough time in the day for {periodsNum || "every"} period{periodsNum === 1 ? "" : "s"} — shorten a
              break or extend the school day.
            </p>
          )}
        </div>

        {strandedBreaks.length > 0 && (
          <p className="mt-3 text-xs" style={{ color: "var(--accent-mark)" }}>
            {strandedBreaks.map((b) => `"${b.label}" (after period ${b.after_period})`).join(", ")} no longer fit{strandedBreaks.length === 1 ? "s" : ""} with only {periodsNum} period{periodsNum === 1 ? "" : "s"} — remove {strandedBreaks.length === 1 ? "it" : "them"} or increase periods per day before saving.
          </p>
        )}
        {error && <p className="mt-3 text-xs" style={{ color: "var(--accent-mark)" }}>{error}</p>}
        {saved && !error && <p className="mt-3 text-xs" style={{ color: "var(--status-good)" }}>Saved.</p>}

        <button type="submit" disabled={busy || !schedule || strandedBreaks.length > 0} className="accent-fill mt-4 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
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

  async function addTeacher(name: string, code: string, maxPeriodsPerDay: number | null, subjectIds: number[]) {
    const created = await api.post<TtTeacher>("/timetable/teachers", { name, code, max_periods_per_day: maxPeriodsPerDay, subject_ids: subjectIds });
    setTeachers((prev) => [...(prev ?? []), created]);
  }

  async function deleteTeacher(id: number) {
    await api.del(`/timetable/teachers/${id}`);
    setTeachers((prev) => prev?.filter((t) => t.id !== id) ?? prev);
  }

  async function updateTeacherSubjects(teacherId: number, subjectIds: number[]) {
    const updated = await api.put<TtTeacher>(`/timetable/teachers/${teacherId}/subjects`, { subject_ids: subjectIds });
    setTeachers((prev) => prev?.map((t) => (t.id === teacherId ? updated : t)) ?? prev);
  }

  async function saveConfig(next: TtSchoolConfig) {
    const updated = await api.put<TtSchoolConfig>("/timetable/config", next);
    setConfig(updated);
  }

  async function runGenerate(): Promise<TtGenerateResult> {
    return api.post<TtGenerateResult>("/timetable/generate");
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
        {loaded && tab === "teachers" && (
          <TeachersTab
            teachers={teachers}
            subjects={subjects}
            config={config}
            onAdd={addTeacher}
            onDelete={deleteTeacher}
            onUpdateSubjects={updateTeacherSubjects}
          />
        )}
        {loaded && tab === "assignments" && <AssignmentsTab classes={classes} subjects={subjects} teachers={teachers} />}
        {loaded && tab === "timetable" && <GeneratedTimetableTab classes={classes} config={config} onGenerate={runGenerate} />}
        {loaded && tab === "schedule" && <ScheduleTab config={config} onSave={saveConfig} />}
      </div>
    </section>
  );
}
