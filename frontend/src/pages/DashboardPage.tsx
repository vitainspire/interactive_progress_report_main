import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { MultiLineChart, SimpleBarChart } from "../components/Charts";
import { FloatingAskButton } from "../components/FloatingAskButton";
import {
  ArrowDownIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  CalendarCheckIcon,
  PeopleIcon,
  XCircleIcon,
} from "../components/Icons";
import { StatTile } from "../components/StatTile";
import { sectionColor } from "../palette";
import type { DashboardData, FailureRow, Student } from "../types";

// Severity bands for a raw count of students (e.g. "how many failed this
// subject") — deliberately keyed off the count itself, not a percentage,
// so a bar's color always matches the metric the chart is actually showing.
function failCountColor(failCount: number): string {
  if (failCount >= 10) return "var(--accent-mark)";
  if (failCount >= 5) return "var(--accent-gold)";
  return "var(--status-good)";
}

function TrendIcon({ delta }: { delta: number | null }) {
  if (delta === null) return null;
  if (delta > 1) return <ArrowUpIcon size={14} />;
  if (delta < -1) return <ArrowDownIcon size={14} />;
  return <ArrowRightIcon size={14} />;
}

function scrollToRef(ref: React.RefObject<HTMLElement | null>) {
  ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const classId = Number(useParams().classId);
  const [data, setData] = useState<DashboardData | null>(null);
  const [students, setStudents] = useState<Student[] | null>(null);
  const [failures, setFailures] = useState<FailureRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const attentionListRef = useRef<HTMLElement | null>(null);
  const performanceRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setData(null);
    setStudents(null);
    setFailures(null);
    setError(null);
    api.get<DashboardData>(`/dashboard?class_id=${classId}`).then(setData).catch((e) => setError(e.message));
    api.get<Student[]>(`/students?class_id=${classId}`).then(setStudents).catch(() => {});
  }, [classId]);

  useEffect(() => {
    const latestPhase = data?.phases.at(-1)?.code;
    if (!latestPhase) return;
    api.get<FailureRow[]>(`/classes/failures?class_id=${classId}&phase=${encodeURIComponent(latestPhase)}`).then(setFailures).catch(() => {});
  }, [data, classId]);

  const computed = useMemo(() => {
    if (!data || !students) return null;

    const overallByPhase = data.phases
      .map((p) => data.phase_section_summary.find((r) => r.phase_code === p.code && r.section === null))
      .filter((r): r is NonNullable<typeof r> => !!r);
    const passRates = overallByPhase.map((o) => (o.passed + o.failed > 0 ? (o.passed / (o.passed + o.failed)) * 100 : null));
    const latestPassRate = passRates.at(-1) ?? null;
    const prevPassRate = passRates.length > 1 ? passRates.at(-2)! : null;
    const passRateDelta = latestPassRate !== null && prevPassRate !== null ? Math.round((latestPassRate - prevPassRate) * 10) / 10 : null;

    const withAttendance = students.filter((s) => s.total_present && s.total_working_days);
    const avgAttendance = withAttendance.length
      ? withAttendance.reduce((sum, s) => sum + (s.total_present! / s.total_working_days!) * 100, 0) / withAttendance.length
      : null;
    const lowAttendanceCount = withAttendance.filter((s) => (s.total_present! / s.total_working_days!) * 100 < 75).length;

    const attention = students
      .map((s) => {
        const reasons: string[] = [];
        let severity = 0;
        if (s.latest_result?.toUpperCase() === "FAIL") {
          reasons.push(`Failed ${s.latest_phase_code}`);
          severity += 2;
        }
        const pct = s.total_present && s.total_working_days ? Math.round((s.total_present / s.total_working_days) * 1000) / 10 : null;
        if (pct !== null && pct < 75) {
          reasons.push(`Attendance ${pct}%`);
          severity += 1;
        }
        return { student: s, reasons, severity, attendancePct: pct };
      })
      .filter((a) => a.reasons.length > 0)
      .sort((a, b) => b.severity - a.severity || (a.attendancePct ?? 100) - (b.attendancePct ?? 100));

    const attentionBySection = data.sections.map((sec) => {
      const total = students.filter((s) => s.section === sec).length;
      const count = attention.filter((a) => a.student.section === sec).length;
      return { section: sec, count, total, pct: total > 0 ? Math.round((count / total) * 1000) / 10 : 0 };
    });

    const sectionSeries = data.sections.map((sec) => ({ key: sec, label: `Section ${sec}`, color: sectionColor(sec) }));
    const sectionChartData = data.phases.map((p) => {
      const row: Record<string, number | null | string> = { name: p.code };
      for (const sec of data.sections) {
        const r = data.phase_section_summary.find((x) => x.phase_code === p.code && x.section === sec);
        row[sec] = r && r.average_total != null && r.max_total ? Math.round((r.average_total / r.max_total) * 1000) / 10 : null;
      }
      return row;
    });

    const failCountBySubject = new Map<string, number>();
    for (const f of failures ?? []) {
      failCountBySubject.set(f.subject, (failCountBySubject.get(f.subject) ?? 0) + 1);
    }
    const subjectStruggle = data.latest_phase_subject_averages
      .map((s) => ({
        subject: s.subject,
        pct: Math.round((s.average / s.max_marks) * 1000) / 10,
        failCount: failCountBySubject.get(s.subject) ?? 0,
      }))
      .sort((a, b) => b.failCount - a.failCount || a.pct - b.pct);

    return { latestPassRate, passRateDelta, avgAttendance, lowAttendanceCount, attention, attentionBySection, sectionSeries, sectionChartData, subjectStruggle };
  }, [data, students, failures]);

  if (error) return <ErrorBanner message={error} />;
  if (!data || !computed) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  if (data.total_students === 0) {
    return (
      <div className="text-center">
        <p style={{ color: "var(--text-secondary)" }}>No data loaded yet.</p>
        <Link to={`/c/${classId}/uploads`} className="mt-2 inline-block text-sm font-medium" style={{ color: "var(--accent)" }}>
          Upload a progress sheet →
        </Link>
      </div>
    );
  }

  const { latestPassRate, passRateDelta, avgAttendance, lowAttendanceCount, attention, attentionBySection, sectionSeries, sectionChartData, subjectStruggle } = computed;
  const latestPhase = data.phases.at(-1)?.code ?? "";

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
        Class Overview
      </h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile
          label="Students"
          value={data.total_students}
          index={0}
          icon={<PeopleIcon size={14} />}
          onClick={() => navigate(`/c/${classId}/sections`)}
        />
        <StatTile
          label={`Pass rate · ${latestPhase}`}
          value={latestPassRate !== null ? `${latestPassRate.toFixed(1)}%` : "-"}
          sub={passRateDelta !== null ? `${passRateDelta > 0 ? "+" : ""}${passRateDelta} pts vs previous exam` : undefined}
          accent={latestPassRate !== null && latestPassRate < 50 ? "mark" : latestPassRate !== null && latestPassRate < 75 ? "gold" : "default"}
          icon={<TrendIcon delta={passRateDelta} />}
          index={1}
          onClick={() => scrollToRef(performanceRef)}
        />
        <StatTile
          label="Avg attendance"
          value={avgAttendance !== null ? `${avgAttendance.toFixed(1)}%` : "-"}
          sub={lowAttendanceCount > 0 ? `${lowAttendanceCount} student${lowAttendanceCount === 1 ? "" : "s"} below 75%` : "everyone above 75%"}
          accent={avgAttendance !== null && avgAttendance < 75 ? "mark" : avgAttendance !== null && avgAttendance < 90 ? "gold" : "default"}
          icon={<CalendarCheckIcon size={14} />}
          index={2}
          onClick={() => scrollToRef(attentionListRef)}
        />
        <StatTile
          label="Need attention"
          value={attention.length}
          sub={attention.length > 0 ? "failed latest exam or low attendance" : "no one flagged right now"}
          accent={attention.length > 0 ? "mark" : "default"}
          icon={<XCircleIcon size={14} />}
          index={3}
          onClick={() => scrollToRef(attentionListRef)}
        />
      </div>

      {attention.length > 0 && (
        <section ref={attentionListRef} className="soft-card reveal p-5" style={{ animationDelay: "230ms" }}>
          <h2 className="section-bar text-base font-medium">Students needing attention</h2>
          <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
            Everyone who failed {latestPhase} or has attendance below 75%, worst first — talk to these students or their parents first.
          </p>
          <div className="mt-3 max-h-80 overflow-y-auto overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Student</th>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Section</th>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Why</th>
                </tr>
              </thead>
              <tbody>
                {attention.map((a) => (
                  <tr key={a.student.id} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                    <td className="px-3 py-2">
                      <Link to={`/students/${a.student.id}`} className="font-medium hover:underline" style={{ color: "var(--accent)" }}>
                        {a.student.name}
                      </Link>
                    </td>
                    <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>
                      <span className="inline-flex items-center gap-2">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: sectionColor(a.student.section) }} />
                        {a.student.section}
                      </span>
                    </td>
                    <td className="px-3 py-2" style={{ color: "var(--accent-mark)" }}>{a.reasons.join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="soft-card reveal p-5" style={{ animationDelay: "280ms" }}>
        <h2 className="section-bar text-base font-medium">Attention needed, by section</h2>
        <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
          Share of each section failing their latest exam or below 75% attendance.
        </p>
        {attention.length === 0 ? (
          <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
            Nobody is currently flagged. 🎉
          </p>
        ) : (
          <>
            <div className="mt-3">
              <SimpleBarChart
                data={attentionBySection.map((s) => ({ name: `Section ${s.section}`, value: s.pct }))}
                colorByIndex={(i) => failCountColor(attentionBySection[i].count)}
                valueLabel="%"
              />
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Section</th>
                    <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Need attention</th>
                    <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Share</th>
                  </tr>
                </thead>
                <tbody>
                  {attentionBySection.map((s) => (
                    <tr key={s.section} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                      <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>
                        <span className="inline-flex items-center gap-2">
                          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: sectionColor(s.section) }} />
                          Section {s.section}
                        </span>
                      </td>
                      <td className="font-mono px-3 py-2 text-right" style={{ color: "var(--text-primary)" }}>
                        {s.count} / {s.total}
                      </td>
                      <td className="font-mono px-3 py-2 text-right" style={{ color: s.count > 0 ? "var(--accent-mark)" : "var(--text-primary)" }}>
                        {s.pct}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section ref={performanceRef} className="soft-card reveal p-5" style={{ animationDelay: "350ms" }}>
        <h2 className="section-bar text-base font-medium">Section performance across exams</h2>
        <div className="mt-3">
          <MultiLineChart categories={data.phases.map((p) => p.code)} series={sectionSeries} data={sectionChartData} valueLabel="%" />
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Section</th>
                {data.phases.map((p) => (
                  <th key={p.code} className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
                    {p.code}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.sections.map((sec) => (
                <tr key={sec} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                  <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: sectionColor(sec) }} />
                      Section {sec}
                    </span>
                  </td>
                  {data.phases.map((p) => {
                    const row = sectionChartData.find((r) => r.name === p.code);
                    const val = row?.[sec];
                    return (
                      <td key={p.code} className="font-mono px-3 py-2 text-right" style={{ color: "var(--text-primary)" }}>
                        {typeof val === "number" ? `${val}%` : "-"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {subjectStruggle.length > 0 && (
        <section className="soft-card reveal p-5" style={{ animationDelay: "420ms" }}>
          <h2 className="section-bar text-base font-medium">
            Where students are struggling most <span className="opacity-75">— {latestPhase}</span>
          </h2>
          <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
            Number of students who failed each subject — the clearest sign of where to focus extra help.
          </p>
          <div className="mt-3">
            <SimpleBarChart
              data={subjectStruggle.map((s) => ({ name: s.subject, value: s.failCount }))}
              colorByIndex={(i) => failCountColor(subjectStruggle[i].failCount)}
              valueLabel="failing"
            />
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Subject</th>
                  <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Students failing</th>
                  <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Class average</th>
                </tr>
              </thead>
              <tbody>
                {subjectStruggle.map((s) => (
                  <tr key={s.subject} className="border-t" style={{ borderColor: "var(--gridline)" }}>
                    <td className="px-3 py-2" style={{ color: "var(--text-primary)" }}>{s.subject}</td>
                    <td className="font-mono px-3 py-2 text-right" style={{ color: s.failCount > 0 ? "var(--accent-mark)" : "var(--text-primary)" }}>
                      {s.failCount}
                    </td>
                    <td className="font-mono px-3 py-2 text-right" style={{ color: "var(--text-primary)" }}>{s.pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {user?.role === "admin" && <FloatingAskButton classId={classId} />}
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <p className="rounded-xl p-3 text-sm" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
      {message}
    </p>
  );
}
