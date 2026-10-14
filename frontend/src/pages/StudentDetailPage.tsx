import { Fragment, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { MultiLineChart } from "../components/Charts";
import { StudentLoginPanel } from "../components/StudentLoginPanel";
import {
  ArrowDownIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  CheckCircleIcon,
  ChevronIcon,
  SpeakerIcon,
  StopIcon,
  TrophyIcon,
  WaveIcon,
  XCircleIcon,
} from "../components/Icons";
import { StatTile } from "../components/StatTile";
import { ZoneGauge } from "../components/ZoneGauge";
import { useSpeechSynthesis } from "../hooks/useVoice";
import { subjectColor } from "../palette";
import type { StudentDetail } from "../types";

const DIRECTION_LABEL: Record<string, string> = {
  improving: "Improving",
  declining: "Declining",
  stable: "Steady",
  fluctuating: "Mixed",
  single: "One result",
  no_data: "No data",
};

const DIRECTION_COLOR: Record<string, string> = {
  improving: "var(--status-good)",
  declining: "var(--accent-mark)",
  stable: "var(--accent)",
  fluctuating: "var(--accent-gold)",
  single: "var(--text-muted)",
  no_data: "var(--text-muted)",
};

const DIRECTION_SOFT: Record<string, string> = {
  improving: "var(--status-good-soft)",
  declining: "var(--accent-mark-soft)",
  stable: "var(--accent-soft)",
  fluctuating: "var(--accent-gold-soft)",
  single: "var(--gridline)",
  no_data: "var(--gridline)",
};

function titleCase(s: string): string {
  return s.charAt(0) + s.slice(1).toLowerCase();
}

function DirectionIcon({ direction }: { direction: string }) {
  const size = 16;
  switch (direction) {
    case "improving":
      return <ArrowUpIcon size={size} />;
    case "declining":
      return <ArrowDownIcon size={size} />;
    case "stable":
      return <ArrowRightIcon size={size} />;
    case "fluctuating":
      return <WaveIcon size={size} />;
    default:
      return <ArrowRightIcon size={size} />;
  }
}

function DirectionBadge({ direction }: { direction: string }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold"
      style={{ color: DIRECTION_COLOR[direction], background: DIRECTION_SOFT[direction] }}
      title={DIRECTION_LABEL[direction]}
    >
      <DirectionIcon direction={direction} />
      {DIRECTION_LABEL[direction]}
    </span>
  );
}

export function StudentDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [detail, setDetail] = useState<StudentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null);
  const [showAllSubjects, setShowAllSubjects] = useState(false);
  const { speak, stop, speaking, supported } = useSpeechSynthesis();

  useEffect(() => {
    setDetail(null);
    setError(null);
    setExpandedPhase(null);
    setShowAllSubjects(false);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    setError(null);
    api
      .get<StudentDetail>(`/students/${id}?all_subjects=${showAllSubjects}`)
      .then(setDetail)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load this student"));
  }, [id, showAllSubjects]);

  const chart = useMemo(() => {
    if (!detail) return null;
    const categories: string[] = [];
    for (const t of detail.subject_trends) {
      for (const p of t.points) {
        if (!categories.includes(p.phase_code)) categories.push(p.phase_code);
      }
    }
    const series = detail.subject_trends.map((t) => ({
      key: t.subject,
      label: titleCase(t.subject),
      color: subjectColor(t.subject),
    }));
    const data = categories.map((phase) => {
      const row: Record<string, number | null | string> = { name: phase };
      for (const t of detail.subject_trends) {
        const point = t.points.find((p) => p.phase_code === phase);
        row[t.subject] = point ? point.pct : null;
      }
      return row;
    });
    return { categories, series, data };
  }, [detail]);

  if (error) return <p style={{ color: "var(--accent-mark)" }}>{error}</p>;
  if (!detail) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  const { student, exam_summaries, exam_results, subject_trends, attendance_summary, total_students_in_class, subject_restricted, own_subjects, showing_all_subjects } = detail;
  const ownSubjectSet = new Set(own_subjects);
  const latest = exam_summaries.at(-1);
  const attendancePct =
    attendance_summary?.total_present && attendance_summary?.total_working_days
      ? Math.round((attendance_summary.total_present / attendance_summary.total_working_days) * 1000) / 10
      : null;
  const attendanceColor = attendancePct === null ? "var(--text-muted)" : attendancePct >= 90 ? "var(--status-good)" : attendancePct >= 75 ? "var(--accent-gold)" : "var(--accent-mark)";
  const isTopRank = !!latest?.rank && latest.rank <= 3;

  function summaryForVoice(): string {
    const parts = [`${student.name}, section ${student.section}.`];
    if (latest) {
      parts.push(
        `Latest result: ${latest.phase_code}, total ${latest.total_marks} out of ${latest.max_total}, grade ${latest.total_grade}, rank ${latest.rank} out of ${total_students_in_class}.`,
      );
    }
    const declining = subject_trends.filter((t) => t.direction === "declining").map((t) => t.subject);
    if (declining.length) parts.push(`Needs attention in ${declining.join(", ")}.`);
    if (attendancePct !== null) parts.push(`Attendance is ${attendancePct} percent.`);
    return parts.join(" ");
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
            {student.name}
          </h1>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Section {student.section} · {student.gender} · Father: {student.father_name} · Mother: {student.mother_name}
          </p>
          {user?.role === "admin" && <StudentLoginPanel studentId={student.id} />}
          {subject_restricted && (
            <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
              {showing_all_subjects
                ? "Showing every subject for this student."
                : `Showing your subject${own_subjects.length === 1 ? "" : "s"} only (${own_subjects.map(titleCase).join(", ")}).`}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {subject_restricted && (
            <button
              onClick={() => setShowAllSubjects((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-[var(--accent-soft)]"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)", background: "var(--surface-1)" }}
            >
              {showing_all_subjects ? "Show my subject only" : "Show all subjects"}
            </button>
          )}
          {supported && (
            <button
              onClick={() => (speaking ? stop() : speak(summaryForVoice()))}
              className="inline-flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-[var(--accent-soft)]"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)", background: "var(--surface-1)" }}
            >
              {speaking ? <StopIcon size={16} /> : <SpeakerIcon size={16} />}
              {speaking ? "Stop" : "Read summary"}
            </button>
          )}
          <a
            href={api.reportUrl(student.id, showAllSubjects)}
            target="_blank"
            rel="noreferrer"
            className="gradient-fill rounded-full px-4 py-2 text-sm font-semibold text-white shadow-sm"
          >
            View full report
          </a>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Latest phase" value={latest?.phase_code ?? "-"} index={0} />
        <StatTile
          label="Latest total"
          value={latest ? `${latest.total_marks}/${latest.max_total}` : "-"}
          sub={latest?.total_grade ?? undefined}
          index={1}
          accent={latest?.result === "FAIL" ? "mark" : "default"}
          icon={latest ? latest.result === "PASS" ? <CheckCircleIcon size={14} /> : <XCircleIcon size={14} /> : undefined}
        />
        <StatTile
          label="Latest rank"
          value={latest?.rank ? `${latest.rank} / ${total_students_in_class}` : "-"}
          accent="gold"
          index={2}
          icon={isTopRank ? <TrophyIcon size={14} /> : undefined}
        />
        <StatTile
          label="Attendance"
          index={3}
          accent={attendancePct !== null && attendancePct < 75 ? "mark" : attendancePct !== null && attendancePct < 90 ? "gold" : "default"}
          visual={
            attendancePct !== null ? (
              <div>
                <div className="font-mono text-[1.8rem] font-bold leading-none" style={{ color: "var(--text-primary)" }}>
                  {attendancePct}%
                </div>
                <div className="mt-3">
                  <ZoneGauge percent={attendancePct} color={attendanceColor} zoneLabels={["Low", "Fair", "Good"]} />
                </div>
              </div>
            ) : (
              <span style={{ color: "var(--text-muted)" }}>-</span>
            )
          }
        />
      </div>

      {detail.focus_topics.length > 0 && (
        <section className="reveal" style={{ animationDelay: "250ms" }}>
          <h2 className="section-bar text-base font-medium">Suggested focus chapters</h2>
          <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
            Based on the textbook index for subjects currently failing — a starting point until topic-level marks are
            available.
          </p>
          <div className="soft-card mt-2 space-y-3 p-4">
            {detail.focus_topics.map((f) => (
              <div key={f.subject}>
                <div className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: subjectColor(f.subject) }} />
                  {titleCase(f.subject)}
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {f.topics.map((t, i) => (
                    <span
                      key={i}
                      className="rounded-full px-2.5 py-1 text-xs"
                      style={{ background: "var(--accent-soft)", color: "var(--text-secondary)" }}
                    >
                      {t.chapter_no ? `${t.chapter_no}. ` : ""}
                      {t.title}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="reveal" style={{ animationDelay: "280ms" }}>
        <h2 className="section-bar text-base font-medium">Exam history</h2>
        <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
          Click a row to see marks for every subject in that exam.
        </p>
        <div className="soft-card mt-2 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Phase", "Total", "Grade", "Result", "Rank"].map((h) => (
                  <th key={h} className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {exam_summaries.map((r) => {
                const passed = r.result === "PASS";
                const isOpen = expandedPhase === r.phase_code;
                const subjectRows = exam_results.filter((er) => er.phase_code === r.phase_code);
                return (
                  <Fragment key={r.phase_code}>
                    <tr
                      className="cursor-pointer border-t transition-colors hover:bg-[var(--accent-soft)]"
                      style={{ borderColor: "var(--gridline)" }}
                      onClick={() => setExpandedPhase(isOpen ? null : r.phase_code)}
                    >
                      <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>
                        <span className="inline-flex items-center gap-1">
                          <span style={{ color: "var(--text-muted)" }}>
                            <ChevronIcon size={14} open={isOpen} />
                          </span>
                          {r.phase_code}
                        </span>
                      </td>
                      <td className="font-mono px-3 py-2" style={{ color: "var(--text-primary)" }}>{r.total_marks}/{r.max_total}</td>
                      <td className="font-mono px-3 py-2" style={{ color: "var(--text-primary)" }}>{r.total_grade}</td>
                      <td className="px-3 py-2">
                        <span className="inline-flex items-center gap-1.5 font-medium" style={{ color: passed ? "var(--status-good)" : "var(--accent-mark)" }}>
                          {passed ? <CheckCircleIcon size={16} /> : <XCircleIcon size={16} />}
                          {r.result}
                        </span>
                      </td>
                      <td className="font-mono px-3 py-2" style={{ color: "var(--text-primary)" }}>
                        <span className="inline-flex items-center gap-1">
                          {r.rank && r.rank <= 3 && (
                            <span className="shrink-0" style={{ color: "var(--accent-gold)" }}>
                              <TrophyIcon size={14} />
                            </span>
                          )}
                          {r.rank}
                        </span>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr style={{ borderColor: "var(--gridline)" }} className="border-t">
                        <td colSpan={5} className="p-0">
                          <div className="px-4 py-3" style={{ background: "var(--page-plane)" }}>
                            <table className="w-full text-sm">
                              <thead>
                                <tr>
                                  <th className="px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Subject</th>
                                  <th className="px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Marks</th>
                                  <th className="px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Grade</th>
                                  <th className="px-2 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Result</th>
                                </tr>
                              </thead>
                              <tbody>
                                {subjectRows.map((sr) => (
                                  <tr key={sr.subject} className="border-t" style={{ borderColor: "var(--border)" }}>
                                    <td className="px-2 py-1.5" style={{ color: "var(--text-primary)" }}>{titleCase(sr.subject)}</td>
                                    <td className="font-mono px-2 py-1.5" style={{ color: "var(--text-primary)" }}>
                                      {sr.marks ?? "-"}/{sr.max_marks ? Math.round(sr.max_marks) : "-"}
                                    </td>
                                    <td className="font-mono px-2 py-1.5" style={{ color: "var(--text-primary)" }}>{sr.grade ?? "-"}</td>
                                    <td className="px-2 py-1.5">
                                      {sr.is_pass === null ? (
                                        <span style={{ color: "var(--text-muted)" }}>-</span>
                                      ) : (
                                        <span style={{ color: sr.is_pass ? "var(--status-good)" : "var(--accent-mark)" }}>
                                          {sr.is_pass ? <CheckCircleIcon size={15} /> : <XCircleIcon size={15} />}
                                        </span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="reveal" style={{ animationDelay: "350ms" }}>
        <h2 className="section-bar text-base font-medium">Subject performance across exams</h2>
        <div className="soft-card mt-2 p-4">
          {chart && <MultiLineChart categories={chart.categories} series={chart.series} data={chart.data} valueLabel="%" />}

          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Subject</th>
                  {chart?.categories.map((c) => (
                    <th key={c} className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
                      {c}
                    </th>
                  ))}
                  <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Trend</th>
                </tr>
              </thead>
              <tbody>
                {subject_trends.map((t) => (
                  <tr key={t.subject} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                    <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>
                      <span className="inline-flex items-center gap-2">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: subjectColor(t.subject) }} />
                        {titleCase(t.subject)}
                        {showing_all_subjects && ownSubjectSet.has(t.subject) && (
                          <span
                            className="rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                            style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
                          >
                            Yours
                          </span>
                        )}
                      </span>
                    </td>
                    {chart?.categories.map((c) => {
                      const point = t.points.find((p) => p.phase_code === c);
                      return (
                        <td key={c} className="font-mono px-3 py-2 text-right" style={{ color: "var(--text-primary)" }}>
                          {point ? `${point.pct}%` : "-"}
                        </td>
                      );
                    })}
                    <td className="px-3 py-2">
                      <DirectionBadge direction={t.direction} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}
