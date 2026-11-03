import { useEffect, useState } from "react";
import { api } from "../api/client";
import { CalendarIcon, PlusIcon, TrashIcon } from "../components/Icons";
import type { TtCalendarEvent } from "../types";

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

/** One school-wide calendar of holidays and real exam dates — reachable
 * from the account menu (like Syllabus/blueprint review) rather than
 * nested inside the Timetable tool, since it's relevant whether or not a
 * school ever builds a timetable: exam dates feed the Report Card
 * Generator's parent-facing pages, holidays feed the Timetable's
 * substitute-finder. One place to manage it, not duplicated per tool. */
export function CalendarPage() {
  const [events, setEvents] = useState<TtCalendarEvent[] | null>(null);
  const [eventType, setEventType] = useState<"holiday" | "exam">("holiday");
  const [label, setLabel] = useState("");
  const [examKey, setExamKey] = useState("");
  const [startDate, setStartDate] = useState(todayStr);
  const [endDate, setEndDate] = useState(todayStr);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    api
      .get<TtCalendarEvent[]>("/calendar/events")
      .then(setEvents)
      .catch(() => setEvents([]));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!label.trim() || (eventType === "exam" && !examKey.trim())) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/calendar/events", {
        event_type: eventType,
        label: label.trim(),
        exam_key: eventType === "exam" ? examKey.trim() : null,
        start_date: startDate,
        end_date: endDate,
      });
      setLabel("");
      setExamKey("");
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this calendar entry");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    await api.del(`/calendar/events/${id}`);
    setEvents((prev) => prev?.filter((e) => e.id !== id) ?? prev);
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

      <div className="soft-card mt-5 p-5" style={{ borderTop: "3px solid var(--accent)" }}>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Your school's holidays and real exam dates — one calendar shared by every tool. Holidays are skipped when
          finding substitutes in Dynamic Timetable; exam dates show up as real dates on the parent-facing report
          instead of just an exam name.
        </p>

        <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-2">
          <div className="w-36">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              Type
            </label>
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value as "holiday" | "exam")}
              className="w-full rounded-md border px-3 py-2 text-sm font-medium"
              style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
            >
              <option value="holiday">Holiday</option>
              <option value="exam">Exam date</option>
            </select>
          </div>
          <div className="w-44">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              {eventType === "holiday" ? "Holiday name" : "Exam name"}
            </label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={eventType === "holiday" ? "e.g. Diwali" : "e.g. SA-1"}
              required
            />
          </div>
          {eventType === "exam" && (
            <div className="w-28">
              <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
                Exam code
              </label>
              <input type="text" value={examKey} onChange={(e) => setExamKey(e.target.value)} placeholder="e.g. SA-1" required />
            </div>
          )}
          <div className="w-40">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              From
            </label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
          </div>
          <div className="w-40">
            <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
              To
            </label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} required />
          </div>
          <button type="submit" disabled={busy} className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
            <PlusIcon size={14} />
            Add
          </button>
        </form>
        {eventType === "exam" && (
          <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
            The exam code must match an exam already used on a marks sheet (e.g. "FA-1", "SA-1") for the date to show
            up on a parent's report.
          </p>
        )}
        {error && (
          <p className="mt-2 text-xs" style={{ color: "var(--accent-mark)" }}>
            {error}
          </p>
        )}
      </div>

      {events === null && (
        <p className="mt-5 text-sm" style={{ color: "var(--text-secondary)" }}>
          Loading…
        </p>
      )}

      {events && events.length === 0 && (
        <div className="soft-card mt-5 flex flex-col items-center p-10 text-center" style={{ borderTop: "3px solid var(--accent)" }}>
          <span
            className="flex h-14 w-14 items-center justify-center rounded-2xl"
            style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
          >
            <CalendarIcon size={24} />
          </span>
          <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            No holidays or exam dates added yet
          </p>
          <p className="mx-auto mt-1 max-w-sm text-sm" style={{ color: "var(--text-secondary)" }}>
            Add one above — it'll be used right away wherever this app needs a real date.
          </p>
        </div>
      )}

      {events && events.length > 0 && (
        <div className="soft-card mt-5 divide-y p-2" style={{ borderColor: "var(--border)" }}>
          {events.map((ev) => (
            <div key={ev.id} className="flex items-center justify-between gap-3 px-3 py-2.5">
              <div className="min-w-0 flex-1">
                <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  {ev.event_type === "holiday" ? "🎉" : "📝"} {ev.label}
                  {ev.exam_key ? ` (${ev.exam_key})` : ""}
                </span>
                <span className="ml-2 text-xs" style={{ color: "var(--text-muted)" }}>
                  {formatRange(ev)}
                </span>
              </div>
              <button
                type="button"
                onClick={() => remove(ev.id)}
                title="Delete"
                className="flex h-8 w-8 flex-none items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-mark-soft)]"
                style={{ color: "var(--text-muted)" }}
              >
                <TrashIcon size={15} />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
