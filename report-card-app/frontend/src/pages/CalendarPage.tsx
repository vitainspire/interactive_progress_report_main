import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { CalendarIcon, ChevronDownIcon, PlusIcon, TrashIcon } from "../components/Icons";
import type { CalendarOverview, ExamPlanType, TtCalendarEvent } from "../types";

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_LABELS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** A visual month grid — Sun..Sat columns, every day a cell, events shown
 * directly on the date(s) they cover. Reads straight off the same event
 * list the List view uses; no separate data source. */
function MonthGrid({
  year, month, events, onDayClick,
}: {
  year: number; month: number; events: TtCalendarEvent[]; onDayClick: (dateStr: string) => void;
}) {
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: (number | null)[] = [];
  for (let i = 0; i < firstWeekday; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  const weeks: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));

  function eventsOn(day: number): TtCalendarEvent[] {
    const dateStr = `${year}-${pad2(month + 1)}-${pad2(day)}`;
    return events.filter((e) => e.start_date <= dateStr && e.end_date >= dateStr);
  }

  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr>
          {WEEKDAY_LABELS.map((d) => (
            <th key={d} className="pb-2 text-center text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
              {d}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {weeks.map((week, wi) => (
          <tr key={wi}>
            {week.map((day, di) => (
              <td
                key={di}
                className={`h-24 w-[14.28%] align-top border p-1 ${day !== null ? "cursor-pointer transition-colors hover:bg-[var(--accent-soft)]" : ""}`}
                style={{ borderColor: "var(--border)" }}
                onClick={day !== null ? () => onDayClick(`${year}-${pad2(month + 1)}-${pad2(day)}`) : undefined}
              >
                {day !== null && (
                  <>
                    <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                      {day}
                    </div>
                    <div className="mt-0.5 space-y-0.5">
                      {eventsOn(day).map((e) => (
                        <div
                          key={e.id}
                          className="truncate rounded px-1 py-0.5 text-[10px] font-semibold"
                          style={
                            e.event_type === "holiday"
                              ? { background: "var(--status-good-soft)", color: "var(--status-good)" }
                              : { background: "var(--accent-soft)", color: "var(--accent)" }
                          }
                          title={e.label}
                        >
                          {e.label}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ExamTypeRow({
  type,
  occurrences,
  onAddOccurrence,
  onDelete,
}: {
  type: ExamPlanType;
  occurrences: TtCalendarEvent[];
  onAddOccurrence: (typeName: string, examKey: string, startDate: string, endDate: string) => Promise<void>;
  onDelete: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [examKey, setExamKey] = useState(`${type.name} ${occurrences.length + 1}`);
  const [startDate, setStartDate] = useState(todayStr);
  const [endDate, setEndDate] = useState(todayStr);
  const [busy, setBusy] = useState(false);

  async function addOccurrence(e: React.FormEvent) {
    e.preventDefault();
    if (!examKey.trim()) return;
    setBusy(true);
    try {
      await onAddOccurrence(type.name, examKey.trim(), startDate, endDate);
      setExamKey(`${type.name} ${occurrences.length + 2}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-t first:border-t-0" style={{ borderColor: "var(--border)" }}>
      <button type="button" onClick={() => setExpanded((v) => !v)} className="flex w-full items-center justify-between gap-3 py-2.5 text-left">
        <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          {type.name}
        </span>
        <span className="flex items-center gap-3">
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {occurrences.length} of {type.count_per_year} dated
          </span>
          <ChevronDownIcon size={15} className={expanded ? "rotate-180 transition-transform" : "transition-transform"} />
        </span>
      </button>
      {expanded && (
        <div className="pb-3 pl-2">
          {occurrences.map((o) => (
            <div key={o.id} className="flex items-center justify-between gap-2 py-1">
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                {o.exam_key} — {o.start_date === o.end_date ? o.start_date : `${o.start_date} – ${o.end_date}`}
              </span>
              <button type="button" onClick={() => onDelete(o.id)} className="flex-none" style={{ color: "var(--text-muted)" }}>
                <TrashIcon size={13} />
              </button>
            </div>
          ))}
          <form onSubmit={addOccurrence} className="mt-2 flex flex-wrap items-end gap-2">
            <div className="w-32">
              <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Exam code
              </label>
              <input type="text" value={examKey} onChange={(e) => setExamKey(e.target.value)} className="text-sm" />
            </div>
            <div className="w-36">
              <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                From
              </label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="text-sm" />
            </div>
            <div className="w-36">
              <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                To
              </label>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="text-sm" />
            </div>
            <button type="submit" disabled={busy} className="flex items-center gap-1 rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-60" style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}>
              <PlusIcon size={12} />
              Add date
            </button>
          </form>
          <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
            The exam code must match an exam already used on a marks sheet (e.g. "FA-1") for the date to show up on a
            parent's report.
          </p>
        </div>
      )}
    </div>
  );
}

function formatDateHeading(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00`);
  return `${MONTH_LABELS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}

/** Opened by clicking a day in the month grid — shows what's already on
 * that date (editable in place) plus a form to add something new starting
 * there, so a teacher doesn't have to hunt through the List view or the
 * Exam Plan section to fix a single date. */
function DayModal({
  date, events, examTypes, onClose, onSave, onDelete, onAdd,
}: {
  date: string;
  events: TtCalendarEvent[];
  examTypes: ExamPlanType[];
  onClose: () => void;
  onSave: (id: number, label: string, examKey: string | null, planType: string | null, startDate: string, endDate: string) => Promise<void>;
  onDelete: (id: number) => void;
  onAdd: (eventType: "holiday" | "exam", label: string, examKey: string | null, planType: string | null, startDate: string, endDate: string) => Promise<void>;
}) {
  const [addType, setAddType] = useState<"holiday" | "exam">("holiday");
  const [addLabel, setAddLabel] = useState("");
  const [addExamKey, setAddExamKey] = useState("");
  const [addPlanType, setAddPlanType] = useState("");
  const [addEnd, setAddEnd] = useState(date);
  const [addBusy, setAddBusy] = useState(false);

  async function submitAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!addLabel.trim()) return;
    if (addType === "exam" && !addExamKey.trim()) return;
    setAddBusy(true);
    try {
      await onAdd(addType, addLabel.trim(), addType === "exam" ? addExamKey.trim() : null, addType === "exam" ? addPlanType || null : null, date, addEnd);
      setAddLabel("");
      setAddExamKey("");
      setAddPlanType("");
      setAddEnd(date);
    } finally {
      setAddBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "rgba(15, 23, 42, 0.45)" }} onClick={onClose}>
      <div className="soft-card w-full max-w-md max-h-[85vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
            {formatDateHeading(date)}
          </h3>
          <button type="button" onClick={onClose} className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
            Close
          </button>
        </div>

        {events.length > 0 ? (
          <div className="mt-3 space-y-3">
            {events.map((ev) => (
              <DayEventRow key={ev.id} event={ev} onSave={onSave} onDelete={onDelete} />
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs" style={{ color: "var(--text-secondary)" }}>
            Nothing on this date yet.
          </p>
        )}

        <form onSubmit={submitAdd} className="mt-4 space-y-2 border-t pt-3" style={{ borderColor: "var(--border)" }}>
          <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
            Add something on this date
          </p>
          <div className="flex gap-2">
            <select
              value={addType}
              onChange={(e) => setAddType(e.target.value as "holiday" | "exam")}
              className="rounded-md border px-2 py-1.5 text-xs font-medium"
              style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
            >
              <option value="holiday">Holiday</option>
              <option value="exam">Exam date</option>
            </select>
            <input
              type="text"
              value={addLabel}
              onChange={(e) => setAddLabel(e.target.value)}
              placeholder={addType === "holiday" ? "e.g. Diwali" : "e.g. Unit Test (UT-2)"}
              className="min-w-0 flex-1 text-sm"
              required
            />
          </div>
          {addType === "exam" && (
            <div className="flex gap-2">
              <select
                value={addPlanType}
                onChange={(e) => setAddPlanType(e.target.value)}
                className="flex-1 rounded-md border px-2 py-1.5 text-xs font-medium"
                style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
              >
                <option value="">No exam type</option>
                {examTypes.map((t) => (
                  <option key={t.id} value={t.name}>
                    {t.name}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={addExamKey}
                onChange={(e) => setAddExamKey(e.target.value)}
                placeholder="Exam code, e.g. FA-1"
                className="flex-1 text-sm"
                required
              />
            </div>
          )}
          <div className="flex items-center gap-2">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Through
            </label>
            <input type="date" value={addEnd} min={date} onChange={(e) => setAddEnd(e.target.value)} className="text-sm" />
            <button type="submit" disabled={addBusy} className="ml-auto flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60" style={{ background: "var(--accent)" }}>
              <PlusIcon size={12} />
              Add
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DayEventRow({
  event,
  onSave,
  onDelete,
}: {
  event: TtCalendarEvent;
  onSave: (id: number, label: string, examKey: string | null, planType: string | null, startDate: string, endDate: string) => Promise<void>;
  onDelete: (id: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(event.label);
  const [startDate, setStartDate] = useState(event.start_date);
  const [endDate, setEndDate] = useState(event.end_date);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await onSave(event.id, label.trim() || event.label, event.exam_key, event.plan_type, startDate, endDate);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  }

  if (!editing) {
    return (
      <div className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5" style={{ background: "var(--surface-2)" }}>
        <span className="text-sm" style={{ color: "var(--text-primary)" }}>
          {event.event_type === "holiday" ? "🎉" : "📝"} {event.label}
        </span>
        <span className="flex items-center gap-2">
          <button type="button" onClick={() => setEditing(true)} className="text-xs font-semibold" style={{ color: "var(--accent)" }}>
            Edit
          </button>
          <button type="button" onClick={() => onDelete(event.id)} style={{ color: "var(--text-muted)" }}>
            <TrashIcon size={13} />
          </button>
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-1.5 rounded-lg p-2" style={{ background: "var(--surface-2)" }}>
      <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} className="w-full text-sm" />
      <div className="flex items-center gap-2">
        <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="text-xs" />
        <span style={{ color: "var(--text-muted)" }}>–</span>
        <input type="date" value={endDate} min={startDate} onChange={(e) => setEndDate(e.target.value)} className="text-xs" />
        <button type="button" onClick={save} disabled={busy} className="ml-auto rounded-md px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-60" style={{ background: "var(--accent)" }}>
          Save
        </button>
        <button type="button" onClick={() => setEditing(false)} className="text-xs" style={{ color: "var(--text-muted)" }}>
          Cancel
        </button>
      </div>
    </div>
  );
}

/** One school-wide calendar of holidays and real exam dates — reachable
 * from the account menu (like Syllabus/blueprint review) rather than
 * nested inside the Timetable tool, since it's relevant whether or not a
 * school ever builds a timetable: exam dates feed the Report Card
 * Generator's parent-facing pages, holidays feed the Timetable's
 * substitute-finder. One place to manage it, not duplicated per tool. */
export function CalendarPage() {
  const [overview, setOverview] = useState<CalendarOverview | null>(null);
  const [view, setView] = useState<"calendar" | "list">("calendar");
  const [cursor, setCursor] = useState(() => new Date());

  const [yearStart, setYearStart] = useState("");
  const [yearEnd, setYearEnd] = useState("");
  const [weekPattern, setWeekPattern] = useState<"5-day" | "6-day">("6-day");
  const [yearBusy, setYearBusy] = useState(false);
  const [yearSaved, setYearSaved] = useState(false);

  const [newTypeName, setNewTypeName] = useState("");
  const [newTypeCount, setNewTypeCount] = useState(1);
  const [typeBusy, setTypeBusy] = useState(false);

  const [showAddHoliday, setShowAddHoliday] = useState(false);
  const [holidayLabel, setHolidayLabel] = useState("");
  const [holidayStart, setHolidayStart] = useState(todayStr);
  const [holidayEnd, setHolidayEnd] = useState(todayStr);
  const [holidayBusy, setHolidayBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  function refresh() {
    api
      .get<CalendarOverview>("/calendar/overview")
      .then((o) => {
        setOverview(o);
        setYearStart(o.academic_year.start_date ?? "");
        setYearEnd(o.academic_year.end_date ?? "");
        setWeekPattern(o.academic_year.week_pattern);
      })
      .catch(() => setOverview(null));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function saveYear(e: React.FormEvent) {
    e.preventDefault();
    if (!yearStart || !yearEnd) return;
    setYearBusy(true);
    setYearSaved(false);
    setError(null);
    try {
      await api.put("/calendar/year", { start_date: yearStart, end_date: yearEnd, week_pattern: weekPattern });
      setYearSaved(true);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the academic year");
    } finally {
      setYearBusy(false);
    }
  }

  async function addExamType(e: React.FormEvent) {
    e.preventDefault();
    if (!newTypeName.trim()) return;
    setTypeBusy(true);
    setError(null);
    try {
      await api.post("/calendar/exam-types", { name: newTypeName.trim(), count_per_year: newTypeCount });
      setNewTypeName("");
      setNewTypeCount(1);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this exam type");
    } finally {
      setTypeBusy(false);
    }
  }

  async function deleteExamType(id: number) {
    await api.del(`/calendar/exam-types/${id}`);
    refresh();
  }

  async function addOccurrence(typeName: string, examKey: string, startDate: string, endDate: string) {
    await api.post("/calendar/events", {
      event_type: "exam",
      label: `${typeName} (${examKey})`,
      exam_key: examKey,
      plan_type: typeName,
      start_date: startDate,
      end_date: endDate,
    });
    refresh();
  }

  async function addHoliday(e: React.FormEvent) {
    e.preventDefault();
    if (!holidayLabel.trim()) return;
    setHolidayBusy(true);
    setError(null);
    try {
      await api.post("/calendar/events", {
        event_type: "holiday",
        label: holidayLabel.trim(),
        start_date: holidayStart,
        end_date: holidayEnd,
      });
      setHolidayLabel("");
      setShowAddHoliday(false);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this holiday");
    } finally {
      setHolidayBusy(false);
    }
  }

  async function deleteEvent(id: number) {
    await api.del(`/calendar/events/${id}`);
    refresh();
  }

  async function saveEvent(
    id: number, label: string, examKey: string | null, planType: string | null, startDate: string, endDate: string,
  ) {
    await api.put(`/calendar/events/${id}`, {
      event_type: examKey ? "exam" : "holiday",
      label, exam_key: examKey, plan_type: planType, start_date: startDate, end_date: endDate,
    });
    refresh();
  }

  async function addEventOnDate(
    eventType: "holiday" | "exam", label: string, examKey: string | null, planType: string | null, startDate: string, endDate: string,
  ) {
    await api.post("/calendar/events", {
      event_type: eventType, label, exam_key: examKey, plan_type: planType, start_date: startDate, end_date: endDate,
    });
    refresh();
  }

  const selectedDateEvents = useMemo(
    () => (overview?.events ?? []).filter((e) => selectedDate && e.start_date <= selectedDate && e.end_date >= selectedDate),
    [overview, selectedDate],
  );

  const occurrencesByType = useMemo(() => {
    const map = new Map<string, TtCalendarEvent[]>();
    for (const e of overview?.events ?? []) {
      if (e.event_type === "exam" && e.plan_type) {
        if (!map.has(e.plan_type)) map.set(e.plan_type, []);
        map.get(e.plan_type)!.push(e);
      }
    }
    return map;
  }, [overview]);

  function changeMonth(delta: number) {
    setCursor((prev) => new Date(prev.getFullYear(), prev.getMonth() + delta, 1));
  }

  function formatRange(ev: TtCalendarEvent): string {
    return ev.start_date === ev.end_date ? ev.start_date : `${ev.start_date} – ${ev.end_date}`;
  }

  return (
    <section>
      <header
        className="dot-grid-plane-dark relative overflow-hidden rounded-2xl px-6 py-6 sm:px-8 sm:py-7"
        style={{ background: "var(--accent-strong)" }}
      >
        <h1 className="font-serif text-2xl font-medium text-white sm:text-3xl">Academic calendar</h1>
      </header>

      {error && (
        <p className="mt-4 text-sm" style={{ color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}

      {overview === null && (
        <p className="mt-5 text-sm" style={{ color: "var(--text-secondary)" }}>
          Loading…
        </p>
      )}

      {overview && (
        <>
          {/* ---- Academic Year ---- */}
          <div className="soft-card mt-5 p-5" style={{ borderTop: "3px solid var(--accent)" }}>
            <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              Academic year
            </h2>
            <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
              The start and end of your school year — everything below (working days, exam plan, holidays) is
              measured against this range.
            </p>
            <form onSubmit={saveYear} className="mt-3 flex flex-wrap items-end gap-2">
              <div className="w-40">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Start date
                </label>
                <input type="date" value={yearStart} onChange={(e) => { setYearStart(e.target.value); setYearSaved(false); }} required />
              </div>
              <div className="w-40">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  End date
                </label>
                <input type="date" value={yearEnd} onChange={(e) => { setYearEnd(e.target.value); setYearSaved(false); }} required />
              </div>
              <div className="w-36">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  School week
                </label>
                <select
                  value={weekPattern}
                  onChange={(e) => { setWeekPattern(e.target.value as "5-day" | "6-day"); setYearSaved(false); }}
                  className="w-full rounded-md border px-3 py-2 text-sm font-medium"
                  style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
                >
                  <option value="6-day">6-day week</option>
                  <option value="5-day">5-day week</option>
                </select>
              </div>
              <button type="submit" disabled={yearBusy} className="accent-fill rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
                {yearBusy ? "Saving…" : "Save"}
              </button>
              {yearSaved && (
                <span className="text-xs font-medium" style={{ color: "var(--status-good)" }}>
                  Saved.
                </span>
              )}
            </form>
          </div>

          {/* ---- Working capacity ---- */}
          {overview.working_capacity && (
            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="soft-card p-4 text-center">
                <div className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {overview.working_capacity.working_days}
                </div>
                <div className="mt-1 text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                  Working days
                </div>
              </div>
              <div className="soft-card p-4 text-center">
                <div className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {overview.working_capacity.working_hours ?? "—"}
                </div>
                <div className="mt-1 text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                  {overview.working_capacity.working_hours === null ? "Working hours (set school day in Timetable)" : "Working hours"}
                </div>
              </div>
              <div className="soft-card p-4 text-center">
                <div className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
                  {overview.working_capacity.non_working_days}
                </div>
                <div className="mt-1 text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                  Non-working days
                </div>
              </div>
            </div>
          )}

          {/* ---- Exam plan ---- */}
          <div className="soft-card mt-5 p-5" style={{ borderTop: "3px solid var(--accent)" }}>
            <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
              Exam plan
            </h2>
            <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
              How many of each exam type this year (e.g. Unit Test ×4). Open one to add its actual dates.
            </p>

            {overview.exam_types.length > 0 && (
              <div className="mt-3">
                {overview.exam_types.map((t) => (
                  <div key={t.id} className="flex items-center gap-2">
                    <div className="flex-1">
                      <ExamTypeRow type={t} occurrences={occurrencesByType.get(t.name) ?? []} onAddOccurrence={addOccurrence} onDelete={deleteEvent} />
                    </div>
                    <button type="button" onClick={() => deleteExamType(t.id)} className="flex-none" style={{ color: "var(--text-muted)" }} title="Delete this exam type">
                      <TrashIcon size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <form onSubmit={addExamType} className="mt-3 flex flex-wrap items-end gap-2 border-t pt-3" style={{ borderColor: "var(--border)" }}>
              <div className="w-48">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  Exam type
                </label>
                <input type="text" value={newTypeName} onChange={(e) => setNewTypeName(e.target.value)} placeholder="e.g. Unit Test" required />
              </div>
              <div className="w-24">
                <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                  This year
                </label>
                <input type="number" min={1} value={newTypeCount} onChange={(e) => setNewTypeCount(Number(e.target.value))} />
              </div>
              <button type="submit" disabled={typeBusy} className="flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60" style={{ background: "var(--accent)" }}>
                <PlusIcon size={14} />
                Add type
              </button>
            </form>
          </div>

          {/* ---- Holidays: Calendar / List ---- */}
          <div className="soft-card mt-5 p-5" style={{ borderTop: "3px solid var(--accent)" }}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                Holidays &amp; dates
              </h2>
              <div className="flex items-center gap-2">
                <div className="flex rounded-md border p-0.5" style={{ borderColor: "var(--border)" }}>
                  <button
                    type="button"
                    onClick={() => setView("calendar")}
                    className="rounded px-2.5 py-1 text-xs font-semibold"
                    style={view === "calendar" ? { background: "var(--accent)", color: "#fff" } : { color: "var(--text-secondary)" }}
                  >
                    Calendar
                  </button>
                  <button
                    type="button"
                    onClick={() => setView("list")}
                    className="rounded px-2.5 py-1 text-xs font-semibold"
                    style={view === "list" ? { background: "var(--accent)", color: "#fff" } : { color: "var(--text-secondary)" }}
                  >
                    List
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAddHoliday((v) => !v)}
                  className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold"
                  style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
                >
                  <PlusIcon size={13} />
                  New holiday
                </button>
              </div>
            </div>

            {showAddHoliday && (
              <form onSubmit={addHoliday} className="mt-3 flex flex-wrap items-end gap-2 rounded-lg p-3" style={{ background: "var(--surface-2)" }}>
                <div className="w-44">
                  <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    Holiday name
                  </label>
                  <input type="text" value={holidayLabel} onChange={(e) => setHolidayLabel(e.target.value)} placeholder="e.g. Diwali" required />
                </div>
                <div className="w-40">
                  <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    From
                  </label>
                  <input type="date" value={holidayStart} onChange={(e) => setHolidayStart(e.target.value)} required />
                </div>
                <div className="w-40">
                  <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                    To
                  </label>
                  <input type="date" value={holidayEnd} onChange={(e) => setHolidayEnd(e.target.value)} required />
                </div>
                <button type="submit" disabled={holidayBusy} className="accent-fill rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
                  {holidayBusy ? "Adding…" : "Add"}
                </button>
              </form>
            )}

            {view === "calendar" ? (
              <div className="mt-4">
                <div className="flex items-center justify-between">
                  <button type="button" onClick={() => changeMonth(-1)} className="rounded-full p-1.5 hover:bg-[var(--accent-soft)]" style={{ color: "var(--text-secondary)" }}>
                    ‹
                  </button>
                  <div className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                    {MONTH_LABELS[cursor.getMonth()]} {cursor.getFullYear()}
                  </div>
                  <button type="button" onClick={() => changeMonth(1)} className="rounded-full p-1.5 hover:bg-[var(--accent-soft)]" style={{ color: "var(--text-secondary)" }}>
                    ›
                  </button>
                </div>
                <div className="mt-2 overflow-x-auto">
                  <MonthGrid year={cursor.getFullYear()} month={cursor.getMonth()} events={overview.events} onDayClick={setSelectedDate} />
                </div>
              </div>
            ) : (
              <div className="mt-3">
                {overview.events.length === 0 && (
                  <div className="flex flex-col items-center p-8 text-center">
                    <span className="flex h-12 w-12 items-center justify-center rounded-2xl" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
                      <CalendarIcon size={20} />
                    </span>
                    <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
                      Nothing added yet.
                    </p>
                  </div>
                )}
                <div className="divide-y" style={{ borderColor: "var(--border)" }}>
                  {overview.events.map((ev) => (
                    <div key={ev.id} className="flex items-center justify-between gap-3 py-2.5">
                      <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                        {ev.event_type === "holiday" ? "🎉" : "📝"} {ev.label}
                      </span>
                      <span className="flex items-center gap-3">
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                          {formatRange(ev)}
                        </span>
                        <button type="button" onClick={() => deleteEvent(ev.id)} style={{ color: "var(--text-muted)" }}>
                          <TrashIcon size={14} />
                        </button>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {selectedDate && overview && (
        <DayModal
          date={selectedDate}
          events={selectedDateEvents}
          examTypes={overview.exam_types}
          onClose={() => setSelectedDate(null)}
          onSave={saveEvent}
          onDelete={deleteEvent}
          onAdd={addEventOnDate}
        />
      )}
    </section>
  );
}
