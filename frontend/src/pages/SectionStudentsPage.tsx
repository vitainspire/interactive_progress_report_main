import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useClasses } from "../context/ClassesContext";
import { CheckCircleIcon, XCircleIcon } from "../components/Icons";
import type { Student } from "../types";

function StatusBadge({ student }: { student: Student }) {
  if (!student.latest_result) {
    return (
      <span className="inline-flex items-center gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
        —
      </span>
    );
  }
  const passed = student.latest_result.toUpperCase() === "PASS";
  const color = passed ? "var(--status-good)" : "var(--accent-mark)";
  return (
    <span className="inline-flex items-center gap-1.5 font-medium" style={{ color }} title={`${student.latest_phase_code}: ${student.latest_result}`}>
      {passed ? <CheckCircleIcon size={18} /> : <XCircleIcon size={18} />}
      <span className="text-xs">{student.latest_phase_code}</span>
    </span>
  );
}

function AttendanceBar({ student }: { student: Student }) {
  if (!student.total_present || !student.total_working_days) {
    return <span className="text-xs" style={{ color: "var(--text-muted)" }}>—</span>;
  }
  const pct = Math.round((student.total_present / student.total_working_days) * 1000) / 10;
  const color = pct >= 90 ? "var(--status-good)" : pct >= 75 ? "var(--accent-gold)" : "var(--accent-mark)";
  return (
    <div className="flex items-center gap-2" title={`${pct}% attendance`}>
      <div className="h-2 w-16 overflow-hidden rounded-full" style={{ background: "var(--gridline)" }}>
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, pct)}%`, background: color }} />
      </div>
      <span className="font-mono text-xs" style={{ color: "var(--text-secondary)" }}>
        {pct}%
      </span>
    </div>
  );
}

export function SectionStudentsPage() {
  const { section } = useParams();
  const classId = Number(useParams().classId);
  const { classes } = useClasses();
  const classLabel = classes.find((c) => c.id === classId)?.name ?? "";
  const [students, setStudents] = useState<Student[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!section) return;
    const params = new URLSearchParams({ class_id: String(classId), section });
    if (search) params.set("search", search);
    api.get<Student[]>(`/students?${params.toString()}`).then(setStudents);
  }, [classId, section, search]);

  const passed = students.filter((s) => s.latest_result?.toUpperCase() === "PASS").length;
  const failed = students.filter((s) => s.latest_result?.toUpperCase() === "FAIL").length;

  return (
    <div>
      <nav className="text-xs" style={{ color: "var(--text-muted)" }}>
        <Link to={`/c/${classId}/sections`} style={{ color: "var(--accent)" }}>
          {classLabel || "Class"}
        </Link>{" "}
        / Section {section}
      </nav>
      <h1 className="font-display mt-1 text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
        Section {section}
      </h1>
      <div className="mt-1 flex flex-wrap items-center gap-4 text-xs" style={{ color: "var(--text-secondary)" }}>
        <span className="inline-flex items-center gap-1">
          <CheckCircleIcon size={14} className="shrink-0" />
          <span style={{ color: "var(--status-good)" }}>Passed</span> latest exam
        </span>
        <span className="inline-flex items-center gap-1">
          <XCircleIcon size={14} className="shrink-0" />
          <span style={{ color: "var(--accent-mark)" }}>Failed</span> latest exam
        </span>
        <span>Bar = attendance</span>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name…"
          className="rounded-xl border px-4 py-2 text-sm shadow-sm"
          style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
        />
        <span className="font-mono inline-flex items-center gap-4 text-sm" style={{ color: "var(--text-secondary)" }}>
          <span className="inline-flex items-center gap-1" style={{ color: "var(--status-good)" }}>
            <CheckCircleIcon size={15} /> {passed}
          </span>
          <span className="inline-flex items-center gap-1" style={{ color: "var(--accent-mark)" }}>
            <XCircleIcon size={15} /> {failed}
          </span>
        </span>
      </div>

      <div className="soft-card mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>S.No</th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Name</th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Result</th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>Attendance</th>
            </tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <tr key={s.id} className="border-t transition-colors hover:bg-[var(--accent-soft)]" style={{ borderColor: "var(--gridline)" }}>
                <td className="font-mono px-3 py-2" style={{ color: "var(--text-primary)" }}>{s.s_no}</td>
                <td className="px-3 py-2">
                  <Link to={`/students/${s.id}`} className="font-medium hover:underline" style={{ color: "var(--accent)" }}>
                    {s.name}
                  </Link>
                </td>
                <td className="px-3 py-2">
                  <StatusBadge student={s} />
                </td>
                <td className="px-3 py-2">
                  <AttendanceBar student={s} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {students.length === 0 && (
          <p className="p-4 text-center text-sm" style={{ color: "var(--text-muted)" }}>
            No students found.
          </p>
        )}
      </div>
    </div>
  );
}
