import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useClasses } from "../context/ClassesContext";
import { CheckCircleIcon, PeopleIcon, XCircleIcon } from "../components/Icons";
import type { Student } from "../types";

interface SectionStat {
  section: string;
  count: number;
  passed: number;
  failed: number;
}

export function SectionsPage() {
  const classId = Number(useParams().classId);
  const { user } = useAuth();
  const { classes } = useClasses();
  const currentClass = classes.find((c) => c.id === classId);
  const classLabel = currentClass?.name ?? "";
  const [students, setStudents] = useState<Student[] | null>(null);

  useEffect(() => {
    setStudents(null);
    api.get<Student[]>(`/students?class_id=${classId}`).then(setStudents);
  }, [classId]);

  // Every admin-defined section shows up here, even with zero students
  // uploaded yet — sections are no longer purely derived from the data.
  const sectionStats = useMemo<SectionStat[]>(() => {
    if (!students || !currentClass) return [];
    const bySection = new Map<string, Student[]>();
    for (const section of currentClass.sections) bySection.set(section, []);
    for (const s of students) {
      const key = s.section || "—";
      if (!bySection.has(key)) bySection.set(key, []);
      bySection.get(key)!.push(s);
    }
    return Array.from(bySection.entries())
      .map(([section, group]) => ({
        section,
        count: group.length,
        passed: group.filter((s) => s.latest_result?.toUpperCase() === "PASS").length,
        failed: group.filter((s) => s.latest_result?.toUpperCase() === "FAIL").length,
      }))
      .sort((a, b) => a.section.localeCompare(b.section));
  }, [students, currentClass]);

  if (!students) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  return (
    <div>
      {user?.role === "admin" && (
        <nav className="text-xs" style={{ color: "var(--text-muted)" }}>
          <Link to="/manage-classes" style={{ color: "var(--accent)" }}>
            Classes
          </Link>{" "}
          / {classLabel || "Class"}
        </nav>
      )}
      <h1 className="font-display mt-1 text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
        {classLabel || "Class"}
      </h1>
      <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
        Select a section to view its students.
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {sectionStats.map((s, i) => (
          <Link
            key={s.section}
            to={`/c/${classId}/sections/${encodeURIComponent(s.section)}`}
            className="soft-card reveal block p-5 transition-shadow hover:shadow-lg"
            style={{ animationDelay: `${i * 70}ms` }}
          >
            <div className="icon-chip">
              <PeopleIcon size={16} />
            </div>
            <div className="font-display mt-3 text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              Section {s.section}
            </div>
            <div className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
              {s.count} students
            </div>
            {(s.passed > 0 || s.failed > 0) && (
              <div className="font-mono mt-3 flex items-center gap-2 text-xs">
                <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 font-semibold" style={{ background: "var(--status-good-soft)", color: "var(--status-good)" }}>
                  <CheckCircleIcon size={14} /> {s.passed}
                </span>
                <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 font-semibold" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
                  <XCircleIcon size={14} /> {s.failed}
                </span>
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
