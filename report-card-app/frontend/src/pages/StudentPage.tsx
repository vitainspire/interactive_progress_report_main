import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ExternalLinkIcon } from "../components/Icons";
import type { StudentAnalytics, StudentStudyPlan } from "../types";

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

function TrendTag({ trend }: { trend: "up" | "down" | "flat" | null }) {
  if (!trend || trend === "flat") return null;
  const up = trend === "up";
  return (
    <span
      className="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
      style={{
        color: up ? "var(--status-good)" : "var(--accent-mark)",
        background: up ? "var(--status-good-soft)" : "var(--accent-mark-soft)",
      }}
    >
      {up ? "↑" : "↓"} {up ? "improving" : "slipping"}
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

function SubjectTagList({ label, names, color }: { label: string; names: string[]; color: string }) {
  if (names.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
        {label}:
      </span>
      {names.map((n) => (
        <span key={n} className="rounded-full px-2 py-0.5 text-xs font-semibold text-white" style={{ background: color }}>
          {n}
        </span>
      ))}
    </div>
  );
}

export function StudentPage() {
  const { id, studentId } = useParams();
  const batchId = Number(id);
  const studentIdNum = Number(studentId);

  const [data, setData] = useState<StudentAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [studyPlan, setStudyPlan] = useState<StudentStudyPlan | null>(null);

  useEffect(() => {
    api
      .get<StudentAnalytics>(`/batches/${batchId}/students/${studentIdNum}/analytics`)
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load this student's analytics"));
  }, [batchId, studentIdNum]);

  // Fetched separately, after the rest of the page has already rendered —
  // this one makes a real LLM call (and a cache write) that the rest of
  // this page's data doesn't need to wait on, same reasoning as the
  // parent report's own lazily-loaded study plan card.
  useEffect(() => {
    api
      .get<StudentStudyPlan>(`/batches/${batchId}/students/${studentIdNum}/study-plan`)
      .then(setStudyPlan)
      .catch(() => setStudyPlan({ available: false }));
  }, [batchId, studentIdNum]);

  if (error) return <p style={{ color: "var(--accent-mark)" }}>{error}</p>;
  if (!data) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  const reportUrl = api.reportUrl(batchId, [studentIdNum]);

  return (
    <div className="space-y-5">
      <div>
        <nav className="text-xs" style={{ color: "var(--text-muted)" }} aria-label="Breadcrumb">
          <Link to="/dashboard" className="hover:underline" style={{ color: "var(--text-muted)" }}>
            Uploads
          </Link>{" "}
          /{" "}
          <Link to={`/batches/${batchId}`} className="hover:underline" style={{ color: "var(--text-muted)" }}>
            Class
          </Link>{" "}
          / {data.name}
        </nav>
        <div
          className="dot-grid-plane-dark relative mt-2 flex flex-wrap items-center justify-between gap-3 overflow-hidden rounded-2xl px-5 py-4 sm:px-8 sm:py-7"
          style={{ background: "var(--accent-strong)" }}
        >
          <div className="min-w-0">
            <h1 className="font-serif text-lg font-medium leading-tight text-white sm:text-3xl">{data.name}</h1>
            <span
              className="mt-1.5 inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold sm:mt-2 sm:px-2.5 sm:py-1 sm:text-xs"
              style={{ borderColor: "rgba(255,255,255,0.35)", color: "rgba(255,255,255,0.85)" }}
            >
              Section {data.section || "—"} · Roll {data.roll_no || "—"}
            </span>
          </div>
          <a
            href={reportUrl}
            target="_blank"
            rel="noopener"
            className="flex flex-none items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors duration-200 sm:px-4 sm:py-2 sm:text-sm"
            style={{ background: "var(--lp-gold)", color: "var(--accent-strong)" }}
          >
            <ExternalLinkIcon size={14} />
            View report card
          </a>
        </div>
      </div>

      {(data.strengths.length > 0 || data.weak_subjects.length > 0 || data.failing_subjects.length > 0) && (
        <div className="soft-card space-y-2 p-5" style={{ borderTop: "3px solid var(--status-good)" }}>
          <SectionLabel>At a glance</SectionLabel>
          <SubjectTagList label="Strong in" names={data.strengths} color="var(--status-good)" />
          <SubjectTagList label="Needs attention" names={data.weak_subjects} color="#d97706" />
          <SubjectTagList label="Failing" names={data.failing_subjects} color="var(--accent-mark)" />
        </div>
      )}

      {(data.advice_cards.length > 0 || studyPlan?.available) && (
        <div className="soft-card p-5" style={{ borderTop: "3px solid var(--accent)" }}>
          <SectionLabel>Teacher's advice — same wording this student's parent sees</SectionLabel>
          <div className="mt-3 space-y-3">
            {data.advice_cards.map((card, i) => (
              <div key={card.title} className="flex gap-3 border-t pt-3 first:border-t-0 first:pt-0" style={{ borderColor: "var(--border)" }}>
                <span
                  className="flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs font-bold"
                  style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
                >
                  {i + 1}
                </span>
                <div>
                  <div className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                    {card.icon} {card.title}
                  </div>
                  <p className="mt-0.5 text-sm" style={{ color: "var(--text-secondary)" }}>
                    {card.text}
                  </p>
                </div>
              </div>
            ))}
            {studyPlan?.available && (
              <div className="flex gap-3 border-t pt-3" style={{ borderColor: "var(--border)" }}>
                <span
                  className="flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs font-bold"
                  style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
                >
                  {data.advice_cards.length + 1}
                </span>
                <div>
                  <div className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                    📘 Syllabus-based plan — {studyPlan.subject}
                  </div>
                  <p className="mt-0.5 text-sm" style={{ color: "var(--text-secondary)" }}>
                    {studyPlan.plan}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {data.rank_trend.length > 0 && (
        <div className="soft-card p-5">
          <SectionLabel>Rank &amp; overall trend</SectionLabel>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-muted)" }}>
                  <th className="pb-2 text-left font-semibold">Exam</th>
                  <th className="pb-2 text-left font-semibold">Total</th>
                  <th className="pb-2 text-left font-semibold">Grade</th>
                  <th className="pb-2 text-left font-semibold">Rank</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
                {data.rank_trend.map((r) => (
                  <tr key={r.exam}>
                    <td className="py-1.5 font-semibold" style={{ color: "var(--text-primary)" }}>
                      {r.exam}
                    </td>
                    <td className="py-1.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                      {r.total_marks ?? "—"}
                    </td>
                    <td className="py-1.5">
                      <GradeChip grade={r.grade} />
                    </td>
                    <td className="py-1.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                      {r.rank} of {r.class_strength}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.attendance_total && (
        <div className="soft-card p-5">
          <SectionLabel>Attendance</SectionLabel>
          <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
            Present{" "}
            <span className="font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
              {data.attendance_total.present}
            </span>{" "}
            of{" "}
            <span className="font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
              {data.attendance_total.working}
            </span>{" "}
            working days so far (
            {data.attendance_total.working
              ? Math.round((data.attendance_total.present * 100) / data.attendance_total.working)
              : 0}
            %).
          </p>
          {data.attendance_trend.length > 0 && (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-muted)" }}>
                    <th className="pb-2 text-left font-semibold">Month</th>
                    <th className="pb-2 text-left font-semibold">Present</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: "var(--border)" }}>
                  {data.attendance_trend.map((m) => (
                    <tr key={m.month}>
                      <td className="py-1.5 font-semibold" style={{ color: "var(--text-primary)" }}>
                        {m.month}
                      </td>
                      <td className="py-1.5 tabular-nums" style={{ color: "var(--text-secondary)" }}>
                        {m.attended} / {m.working_days || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {data.subjects.length > 0 && (
        <div className="soft-card p-5">
          <SectionLabel>Subjects, exam by exam</SectionLabel>
          <div className="mt-3 space-y-4">
            {data.subjects.map((subj) => (
              <div key={subj.name} className="border-t pt-3 first:border-t-0 first:pt-0" style={{ borderColor: "var(--border)" }}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
                    {subj.name}
                  </span>
                  <TrendTag trend={subj.trend} />
                </div>
                <div className="mt-1.5 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ color: "var(--text-muted)" }}>
                        <th className="pb-1 text-left font-semibold">Exam</th>
                        <th className="pb-1 text-left font-semibold">Marks</th>
                        <th className="pb-1 text-left font-semibold">Grade</th>
                        <th className="pb-1 text-left font-semibold">Class avg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {subj.per_exam.map((p) => (
                        <tr key={p.exam}>
                          <td className="py-1" style={{ color: "var(--text-secondary)" }}>
                            {p.exam}
                          </td>
                          <td className="py-1 tabular-nums" style={{ color: "var(--text-primary)" }}>
                            {p.marks ?? "—"}/{p.max_marks}
                          </td>
                          <td className="py-1">
                            <GradeChip grade={p.grade} />
                          </td>
                          <td className="py-1 tabular-nums" style={{ color: "var(--text-muted)" }}>
                            {p.class_avg ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.exams.length === 0 && (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          No exam marks are on file for this student yet.
        </p>
      )}
    </div>
  );
}
