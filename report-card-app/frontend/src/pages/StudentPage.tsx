import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { PrinterIcon } from "../components/Icons";
import { ReportPreview } from "../components/ReportPreview";
import type { BatchDetail } from "../types";

export function StudentPage() {
  const { id, studentId } = useParams();
  const batchId = Number(id);
  const studentIdNum = Number(studentId);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const [detail, setDetail] = useState<BatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<BatchDetail>(`/batches/${batchId}`)
      .then(setDetail)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load this student"));
  }, [batchId]);

  function printReport() {
    iframeRef.current?.contentWindow?.focus();
    iframeRef.current?.contentWindow?.print();
  }

  if (error) return <p style={{ color: "var(--accent-mark)" }}>{error}</p>;
  if (!detail) return <p style={{ color: "var(--text-secondary)" }}>Loading…</p>;

  const student = detail.students.find((s) => s.id === studentIdNum);
  if (!student) return <p style={{ color: "var(--accent-mark)" }}>This student isn't in this upload.</p>;

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
            {detail.name}
          </Link>{" "}
          / {student.name}
        </nav>
        <div className="mt-1 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
              {student.name}
            </h1>
            <span className="pill mt-2 inline-flex">
              Section {student.section || "—"} · Roll {student.roll_no || "—"}
            </span>
          </div>
          <button
            onClick={printReport}
            className="accent-fill flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all duration-200 active:scale-[0.99]"
          >
            <PrinterIcon size={14} />
            Print
          </button>
        </div>
      </div>

      <ReportPreview reportUrl={reportUrl} iframeRef={iframeRef} />
    </div>
  );
}
