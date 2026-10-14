import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import {
  BarChartIcon,
  ExternalLinkIcon,
  FitScreenIcon,
  PrinterIcon,
  SearchIcon,
  SendIcon,
  SettingsIcon,
  TrashIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from "../components/Icons";
import type { BatchDetail, ClassStats, RankedStudent, SendResult, StudentBrief } from "../types";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
        {label}
      </label>
      {children}
    </div>
  );
}

function BatchHeader({ detail, onDelete }: { detail: BatchDetail; onDelete: () => void }) {
  return (
    <div>
      <nav className="text-xs" style={{ color: "var(--text-muted)" }} aria-label="Breadcrumb">
        <Link to="/dashboard" className="hover:underline" style={{ color: "var(--text-muted)" }}>
          Uploads
        </Link>{" "}
        / {detail.name}
      </nav>
      <div className="mt-1 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
            {detail.name}
          </h1>
          <span className="pill mt-2 inline-flex">
            {detail.student_count} students · {detail.exam_codes.join(", ")}
          </span>
        </div>
        <button
          onClick={onDelete}
          className="flex items-center gap-1.5 rounded-md border px-3.5 py-1.5 text-sm font-medium transition-colors duration-200"
          style={{ borderColor: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-mark-soft)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
        >
          <TrashIcon size={14} />
          Delete upload
        </button>
      </div>
    </div>
  );
}

const GRADE_COLORS: Record<string, string> = {
  A1: "var(--status-good)",
  A2: "var(--status-good)",
  B1: "var(--accent)",
  B2: "var(--accent)",
  C1: "#d97706",
  C2: "#d97706",
  D1: "#ea580c",
  D2: "var(--accent-mark)",
};

function gradeColor(grade: string): string {
  return GRADE_COLORS[grade] ?? "var(--text-muted)";
}

function GradeChip({ grade }: { grade: string }) {
  return (
    <span
      className="inline-flex min-w-[2.1em] flex-none items-center justify-center rounded-full px-1.5 py-0.5 text-[11px] font-bold text-white"
      style={{ background: gradeColor(grade) }}
    >
      {grade}
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
      {children}
    </h3>
  );
}

function PassRateRing({ pct }: { pct: number }) {
  return (
    <div
      className="flex h-24 w-24 flex-none items-center justify-center rounded-full"
      style={{ background: `conic-gradient(var(--status-good) ${pct}%, var(--border) 0)` }}
    >
      <div className="flex h-[4.5rem] w-[4.5rem] flex-col items-center justify-center rounded-full" style={{ background: "var(--surface-1)" }}>
        <span className="text-xl font-extrabold tabular-nums" style={{ color: "var(--text-primary)" }}>
          {pct}%
        </span>
        <span className="text-[9px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          Pass rate
        </span>
      </div>
    </div>
  );
}

function StatRow({ dotColor, label, value }: { dotColor: string; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="h-2 w-2 flex-none rounded-full" style={{ background: dotColor }} />
      <span className="flex-1" style={{ color: "var(--text-secondary)" }}>
        {label}
      </span>
      <span className="font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
        {value}
      </span>
    </div>
  );
}

function TrendBadge({ trend }: { trend: ClassStats["exam_trend"] }) {
  const usable = trend.filter((t) => t.avg_pct != null);
  if (usable.length < 2) return null;
  const last = usable[usable.length - 1];
  const prev = usable[usable.length - 2];
  const delta = +(last.avg_pct! - prev.avg_pct!).toFixed(1);
  if (delta === 0) return null;
  const up = delta > 0;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold"
      style={{
        color: up ? "var(--status-good)" : "var(--accent-mark)",
        background: up ? "var(--status-good-soft)" : "var(--accent-mark-soft)",
      }}
      title={`Class average went from ${prev.avg_pct}% in ${prev.exam} to ${last.avg_pct}% in ${last.exam}`}
    >
      {up ? "↑" : "↓"} {Math.abs(delta)} pts vs {prev.exam}
    </span>
  );
}

function GradeDistributionBar({ data }: { data: { grade: string; count: number }[] }) {
  const total = data.reduce((sum, d) => sum + d.count, 0) || 1;
  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full" style={{ background: "var(--border)" }}>
        {data.map((d) => (
          <div
            key={d.grade}
            style={{ width: `${(d.count / total) * 100}%`, background: gradeColor(d.grade) }}
            title={`${d.grade}: ${d.count} students`}
          />
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5">
        {data.map((d) => (
          <div key={d.grade} className="flex items-center gap-1.5 text-xs">
            <span className="h-2 w-2 rounded-full" style={{ background: gradeColor(d.grade) }} />
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>
              {d.grade}
            </span>
            <span style={{ color: "var(--text-muted)" }}>{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SubjectAverageBars({ data }: { data: ClassStats["subject_averages"] }) {
  return (
    <div className="space-y-3">
      {data.map((s) => (
        <div key={s.subject}>
          <div className="flex items-baseline justify-between text-xs">
            <span className="font-medium" style={{ color: "var(--text-primary)" }}>
              {s.subject}
            </span>
            <span className="tabular-nums" style={{ color: "var(--text-muted)" }}>
              {s.avg_marks}/{s.max_marks} · <b style={{ color: "var(--text-secondary)" }}>{s.avg_pct}%</b>
            </span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full" style={{ background: "var(--border)" }}>
            <div
              className="h-full rounded-full transition-[width] duration-500"
              style={{
                width: `${Math.min(100, s.avg_pct)}%`,
                background: s.avg_pct >= 75 ? "var(--status-good)" : s.avg_pct >= 50 ? "var(--accent)" : "var(--accent-mark)",
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function StudentRow({ student, tone }: { student: RankedStudent; tone: "good" | "warn" }) {
  return (
    <div
      className="group flex items-center gap-3 border-b py-2 last:border-b-0"
      style={{ borderColor: "var(--border)" }}
    >
      <span
        className="flex h-6 w-6 flex-none items-center justify-center rounded-full text-[11px] font-bold tabular-nums"
        style={{
          background: tone === "good" ? "var(--accent-soft)" : "var(--accent-mark-soft)",
          color: tone === "good" ? "var(--accent)" : "var(--accent-mark)",
        }}
      >
        {student.rank ?? "–"}
      </span>
      <span className="flex-1 truncate text-sm" style={{ color: "var(--text-primary)" }}>
        {student.name}
      </span>
      <GradeChip grade={student.grade} />
    </div>
  );
}

function StudentLeaderboard({ title, students, tone }: { title: string; students: RankedStudent[]; tone: "good" | "warn" }) {
  return (
    <div>
      <SectionLabel>{title}</SectionLabel>
      <div className="mt-1.5">
        {students.length === 0 ? (
          <p className="py-2 text-xs" style={{ color: "var(--text-muted)" }}>
            Nothing to show yet.
          </p>
        ) : (
          students.map((s) => <StudentRow key={s.id} student={s} tone={tone} />)
        )}
      </div>
    </div>
  );
}

function ClassOverview({ stats }: { stats: ClassStats | null }) {
  return (
    <div className="soft-card p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="icon-chip" style={{ width: "1.75rem", height: "1.75rem" }}>
          <BarChartIcon size={14} />
        </span>
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          Class overview
        </h2>
        {stats?.latest_exam && <span className="pill">{stats.latest_exam}</span>}
        {stats && <TrendBadge trend={stats.exam_trend} />}
      </div>

      {!stats ? (
        <p className="mt-3 text-sm" style={{ color: "var(--text-secondary)" }}>
          Crunching the numbers…
        </p>
      ) : stats.graded_count === 0 ? (
        <p className="mt-3 text-sm" style={{ color: "var(--text-secondary)" }}>
          No graded results yet for this batch.
        </p>
      ) : (
        <>
          <div className="mt-5 flex flex-wrap items-center gap-6">
            <PassRateRing pct={Math.round((stats.pass_count / stats.graded_count) * 100)} />
            <div className="min-w-[10rem] flex-1 space-y-2">
              <StatRow dotColor="var(--status-good)" label="Passed" value={String(stats.pass_count)} />
              <StatRow dotColor="var(--accent-mark)" label="Failed" value={String(stats.fail_count)} />
              <StatRow
                dotColor="var(--accent)"
                label="Avg attendance"
                value={stats.avg_attendance_pct != null ? `${stats.avg_attendance_pct}%` : "—"}
              />
            </div>
          </div>

          {stats.grade_distribution.length > 0 && (
            <div className="mt-5 border-t pt-5" style={{ borderColor: "var(--border)" }}>
              <SectionLabel>Grade distribution</SectionLabel>
              <div className="mt-2.5">
                <GradeDistributionBar data={stats.grade_distribution} />
              </div>
            </div>
          )}

          {stats.subject_averages.length > 0 && (
            <div className="mt-5 border-t pt-5" style={{ borderColor: "var(--border)" }}>
              <SectionLabel>Subject-wise class average</SectionLabel>
              <div className="mt-2.5">
                <SubjectAverageBars data={stats.subject_averages} />
              </div>
            </div>
          )}

          <div className="mt-5 grid grid-cols-1 gap-x-6 gap-y-5 border-t pt-5 sm:grid-cols-2" style={{ borderColor: "var(--border)" }}>
            <StudentLeaderboard title="Top performers" students={stats.top_students} tone="good" />
            <StudentLeaderboard title="Needs attention" students={stats.attention_students} tone="warn" />
          </div>
        </>
      )}
    </div>
  );
}

interface SettingsState {
  name: string;
  schoolName: string;
  faTotal: string;
  saTotal: string;
  faMarks: string;
  saMarks: string;
  strengthOverride: string;
}

function SettingsDrawer({
  settings,
  onChange,
  onSave,
  saving,
  error,
  defaultStrength,
}: {
  settings: SettingsState;
  onChange: (next: Partial<SettingsState>) => void;
  onSave: () => void;
  saving: boolean;
  error: string | null;
  defaultStrength: number;
}) {
  return (
    <details className="soft-card p-5">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-base font-semibold" style={{ color: "var(--text-primary)" }}>
        <span className="icon-chip" style={{ width: "1.75rem", height: "1.75rem" }}>
          <SettingsIcon size={14} />
        </span>
        Batch configuration
      </summary>
      <div className="mt-4 grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-3">
        <div className="space-y-3">
          <Field label="School name">
            <input type="text" value={settings.schoolName} onChange={(e) => onChange({ schoolName: e.target.value })} />
          </Field>
          <Field label="Batch name">
            <input type="text" value={settings.name} onChange={(e) => onChange({ name: e.target.value })} />
          </Field>
          <Field label="Class strength">
            <input
              type="number"
              min={0}
              value={settings.strengthOverride}
              onChange={(e) => onChange({ strengthOverride: e.target.value })}
              placeholder={`auto (${defaultStrength})`}
            />
          </Field>
        </div>
        <div className="space-y-3">
          <Field label="FA exam total">
            <input type="number" value={settings.faTotal} onChange={(e) => onChange({ faTotal: e.target.value })} />
          </Field>
          <Field label="FA marks per subject">
            <input type="number" value={settings.faMarks} onChange={(e) => onChange({ faMarks: e.target.value })} />
          </Field>
        </div>
        <div className="space-y-3">
          <Field label="SA / other exam total">
            <input type="number" value={settings.saTotal} onChange={(e) => onChange({ saTotal: e.target.value })} />
          </Field>
          <Field label="SA / other marks per subject">
            <input type="number" value={settings.saMarks} onChange={(e) => onChange({ saMarks: e.target.value })} />
          </Field>
        </div>
      </div>
      {error && (
        <p className="mt-3 text-sm" style={{ color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}
      <button
        onClick={onSave}
        disabled={saving}
        className="mt-4 rounded-md border px-4 py-2 text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)] disabled:opacity-60"
        style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
      >
        {saving ? "Saving…" : "Apply settings"}
      </button>
    </details>
  );
}

function Toolbar({
  students,
  selected,
  onToggleAll,
  onToggleOne,
  onPrint,
  reportUrl,
  onSendToParents,
  sending,
}: {
  students: StudentBrief[];
  selected: Set<number>;
  onToggleAll: (checked: boolean) => void;
  onToggleOne: (id: number, checked: boolean) => void;
  onPrint: () => void;
  reportUrl: string;
  onSendToParents: () => void;
  sending: boolean;
}) {
  const [studentSearch, setStudentSearch] = useState("");
  const filtered = students.filter((s) => s.name.toLowerCase().includes(studentSearch.trim().toLowerCase()));
  const allSelected = selected.size === students.length;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <details className="relative">
          <summary
            className="cursor-pointer list-none rounded-md border px-4 py-2 text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)]"
            style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
          >
            Select students ({selected.size})
          </summary>
          <div className="soft-card absolute z-10 mt-1 max-h-80 w-64 overflow-hidden" style={{ boxShadow: "var(--shadow-pop)" }}>
            <div className="relative border-b p-2" style={{ borderColor: "var(--border)" }}>
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }}>
                <SearchIcon size={14} />
              </span>
              <input
                type="text"
                value={studentSearch}
                onChange={(e) => setStudentSearch(e.target.value)}
                placeholder="Search students…"
                className="pl-8 text-sm"
              />
            </div>
            <label
              className="flex items-center gap-2 border-b px-3 py-2 text-sm font-semibold"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
            >
              <input type="checkbox" checked={allSelected} onChange={(e) => onToggleAll(e.target.checked)} />
              Select all
            </label>
            <div className="max-h-48 overflow-auto p-2">
              {filtered.map((s) => (
                <label key={s.id} className="flex items-center justify-between gap-2 py-1 text-sm" style={{ color: "var(--text-primary)" }}>
                  <span className="flex items-center gap-2">
                    <input type="checkbox" checked={selected.has(s.id)} onChange={(e) => onToggleOne(s.id, e.target.checked)} />
                    {s.name}
                  </span>
                  {!s.phone.trim() && (
                    <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                      no phone
                    </span>
                  )}
                </label>
              ))}
              {filtered.length === 0 && (
                <p className="py-2 text-center text-xs" style={{ color: "var(--text-muted)" }}>
                  No students match.
                </p>
              )}
            </div>
          </div>
        </details>
        <button onClick={() => onToggleAll(!allSelected)} className="pill transition-colors duration-200 hover:bg-[var(--accent-soft)]">
          {allSelected ? "Clear selection" : "Select all"}
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="pill">
          Showing {selected.size} of {students.length}
        </span>
        <a
          href={reportUrl}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)]"
          style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
        >
          <ExternalLinkIcon size={14} />
          Open in new tab
        </a>
        <button
          onClick={onPrint}
          className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all duration-200 active:scale-[0.99]"
        >
          <PrinterIcon size={14} />
          Print
        </button>
        <button
          onClick={onSendToParents}
          disabled={sending || selected.size === 0}
          className="flex items-center gap-1.5 rounded-md border px-4 py-2 text-sm font-semibold transition-colors duration-200 hover:bg-[var(--accent-soft)] disabled:opacity-60"
          style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
        >
          <SendIcon size={14} />
          {sending ? "Sending…" : "Send to parents"}
        </button>
      </div>
    </div>
  );
}

function ReportPreview({ reportUrl, iframeRef }: { reportUrl: string; iframeRef: React.RefObject<HTMLIFrameElement | null> }) {
  const [zoom, setZoom] = useState(1);
  return (
    <div className="relative">
      <div className="dot-grid-plane overflow-auto rounded-md p-6" style={{ maxHeight: 900, background: "var(--page-plane)" }}>
        <div
          className="mx-auto overflow-hidden rounded-lg"
          style={{
            width: `${100 / zoom}%`,
            transform: `scale(${zoom})`,
            transformOrigin: "top center",
            boxShadow: "var(--shadow-pop)",
          }}
        >
          <iframe ref={iframeRef} src={reportUrl} title="Report card preview" className="h-[1100px] w-full border-0" />
        </div>
      </div>
      <div className="soft-card absolute bottom-4 right-4 flex items-center gap-1 p-1">
        <button
          onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.1).toFixed(2)))}
          aria-label="Zoom out"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-soft)]"
          style={{ color: "var(--text-secondary)" }}
        >
          <ZoomOutIcon size={15} />
        </button>
        <button
          onClick={() => setZoom(1)}
          aria-label="Fit page"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-soft)]"
          style={{ color: "var(--text-secondary)" }}
        >
          <FitScreenIcon size={15} />
        </button>
        <button
          onClick={() => setZoom((z) => Math.min(1.5, +(z + 0.1).toFixed(2)))}
          aria-label="Zoom in"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-soft)]"
          style={{ color: "var(--text-secondary)" }}
        >
          <ZoomInIcon size={15} />
        </button>
      </div>
    </div>
  );
}

export function BatchPage() {
  const { id } = useParams();
  const batchId = Number(id);
  const navigate = useNavigate();
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const [detail, setDetail] = useState<BatchDetail | null>(null);
  const [stats, setStats] = useState<ClassStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [reloadNonce, setReloadNonce] = useState(0);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendResults, setSendResults] = useState<SendResult[] | null>(null);

  const [settings, setSettings] = useState<SettingsState>({
    name: "",
    schoolName: "",
    faTotal: "350",
    saTotal: "600",
    faMarks: "50",
    saMarks: "100",
    strengthOverride: "",
  });

  useEffect(() => {
    api
      .get<BatchDetail>(`/batches/${batchId}`)
      .then((d) => {
        setDetail(d);
        setSelected(new Set(d.students.map((s) => s.id)));
        setSettings({
          name: d.name,
          schoolName: d.school_name,
          faTotal: String(d.fa_total),
          saTotal: String(d.sa_total),
          faMarks: String(d.fa_marks_per_subject),
          saMarks: String(d.sa_marks_per_subject),
          strengthOverride: d.class_strength_override != null ? String(d.class_strength_override) : "",
        });
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load this upload"));

    setStats(null);
    api
      .get<ClassStats>(`/batches/${batchId}/stats`)
      .then(setStats)
      .catch(() => {
        /* overview is a bonus, not required for the page to work */
      });
  }, [batchId]);

  const selectedIds = useMemo(() => [...selected].sort((a, b) => a - b), [selected]);
  const reportUrl = useMemo(() => {
    const base = api.reportUrl(batchId, selectedIds.length === detail?.students.length ? undefined : selectedIds);
    return `${base}&v=${reloadNonce}`;
  }, [batchId, selectedIds, detail, reloadNonce]);

  function toggleAll(checked: boolean) {
    setSelected(checked ? new Set(detail?.students.map((s) => s.id) ?? []) : new Set());
  }

  function toggleOne(studentId: number, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(studentId);
      else next.delete(studentId);
      return next;
    });
  }

  async function saveSettings() {
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        name: settings.name.trim() || undefined,
        school_name: settings.schoolName,
        fa_total: Number(settings.faTotal) || undefined,
        sa_total: Number(settings.saTotal) || undefined,
        fa_marks_per_subject: Number(settings.faMarks) || undefined,
        sa_marks_per_subject: Number(settings.saMarks) || undefined,
      };
      if (settings.strengthOverride.trim()) payload.class_strength_override = Number(settings.strengthOverride);
      else payload.clear_class_strength_override = true;
      const updated = await api.put<BatchDetail>(`/batches/${batchId}/settings`, payload);
      setDetail((prev) => (prev ? { ...prev, ...updated, students: prev.students } : prev));
      setReloadNonce((n) => n + 1);
      api
        .get<ClassStats>(`/batches/${batchId}/stats`)
        .then(setStats)
        .catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  }

  async function deleteBatch() {
    if (!confirm(`Delete "${detail?.name}"? This can't be undone.`)) return;
    await api.del(`/batches/${batchId}`);
    navigate("/dashboard");
  }

  function printSelected() {
    iframeRef.current?.contentWindow?.focus();
    iframeRef.current?.contentWindow?.print();
  }

  async function sendToParents() {
    if (!detail) return;
    setSending(true);
    setSendResults(null);
    try {
      const allSelected = selectedIds.length === detail.students.length;
      const res = await api.post<{ results: SendResult[] }>(`/batches/${batchId}/send-reports`, {
        student_ids: allSelected ? null : selectedIds,
      });
      setSendResults(res.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send reports");
    } finally {
      setSending(false);
    }
  }

  const selectedWithoutPhone = detail ? detail.students.filter((s) => selected.has(s.id) && !s.phone.trim()).length : 0;

  if (error && !detail) return <p style={{ color: "var(--accent-mark)" }}>{error}</p>;
  if (!detail) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  return (
    <div className="space-y-5">
      <BatchHeader detail={detail} onDelete={deleteBatch} />

      <ClassOverview stats={stats} />

      <SettingsDrawer
        settings={settings}
        onChange={(next) => setSettings((prev) => ({ ...prev, ...next }))}
        onSave={saveSettings}
        saving={saving}
        error={error}
        defaultStrength={detail.student_count}
      />

      <Toolbar
        students={detail.students}
        selected={selected}
        onToggleAll={toggleAll}
        onToggleOne={toggleOne}
        onPrint={printSelected}
        reportUrl={reportUrl}
        onSendToParents={sendToParents}
        sending={sending}
      />

      {selectedWithoutPhone > 0 && (
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          {selectedWithoutPhone} of the selected students have no phone number on file and will be skipped when
          sending to parents.
        </p>
      )}

      {sendResults && (
        <div className="soft-card p-5">
          <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
            Send to parents — results
          </h2>
          <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
            Tries WhatsApp first, falls back to SMS if WhatsApp isn't set up or that send fails. Needs a WhatsApp
            Cloud API and/or Twilio SMS account configured on the server first — until then, sends show as
            "failed: not configured" below. Either way, each student's own private report link is generated
            regardless, so you can open it yourself with "View link" to see exactly what a parent would see.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  {["Student", "Channel", "Status", "Detail", "Link"].map((h) => (
                    <th key={h} className="px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sendResults.map((r) => (
                  <tr key={r.student_id} className="border-t" style={{ borderColor: "var(--border)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-primary)" }}>{r.name}</td>
                    <td className="px-2 py-1.5 capitalize" style={{ color: "var(--text-primary)" }}>{r.channel}</td>
                    <td
                      className="px-2 py-1.5 font-medium capitalize"
                      style={{ color: r.status === "sent" ? "var(--status-good)" : r.status === "failed" ? "var(--accent-mark)" : "var(--text-muted)" }}
                    >
                      {r.status}
                    </td>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-muted)" }}>{r.detail || "—"}</td>
                    <td className="px-2 py-1.5">
                      {r.report_url ? (
                        <a href={r.report_url} target="_blank" rel="noreferrer" className="font-medium" style={{ color: "var(--accent)" }}>
                          View link
                        </a>
                      ) : (
                        <span style={{ color: "var(--text-muted)" }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <ReportPreview reportUrl={reportUrl} iframeRef={iframeRef} />
    </div>
  );
}
