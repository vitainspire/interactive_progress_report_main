import { useState } from "react";
import { api } from "../api/client";
import { ChatIcon, EyeIcon, SheetIcon } from "./Icons";
import type { StudentBrief } from "../types";

interface StudentLink {
  report_url: string;
  whatsapp_phone: string | null;
}

/** One row per student with three actions, replacing the old default view
 * of every selected student's full report concatenated into one long
 * iframe. Each action opens in a new tab so working down a long list of
 * students doesn't lose your place:
 *   - WhatsApp: opens a wa.me click-to-chat link pre-filled with that
 *     student's private report link — this app never sends WhatsApp
 *     messages itself (no Cloud API configured here), it just hands the
 *     teacher's own WhatsApp a ready-to-send message.
 *   - Eye: previews the exact parent-facing link before sending it.
 *   - Report: the full teacher-facing report (same view as the dedicated
 *     student page), for a quick look without leaving this list. */
export function StudentActionList({ batchId, students }: { batchId: number; students: StudentBrief[] }) {
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function fetchLink(studentId: number): Promise<StudentLink | null> {
    setError(null);
    setLoadingId(studentId);
    try {
      return await api.get<StudentLink>(`/batches/${batchId}/students/${studentId}/link`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate this student's link");
      return null;
    } finally {
      setLoadingId(null);
    }
  }

  async function openWhatsApp(student: StudentBrief) {
    const link = await fetchLink(student.id);
    if (!link || !link.whatsapp_phone) return;
    const message = `${student.name} గారి ప్రోగ్రెస్ రిపోర్ట్ ఇక్కడ చూడండి: ${link.report_url}`;
    window.open(`https://wa.me/${link.whatsapp_phone}?text=${encodeURIComponent(message)}`, "_blank", "noopener");
  }

  async function previewParentLink(student: StudentBrief) {
    const link = await fetchLink(student.id);
    if (!link) return;
    window.open(link.report_url, "_blank", "noopener");
  }

  function openFullReport(student: StudentBrief) {
    window.open(api.reportUrl(batchId, [student.id]), "_blank", "noopener");
  }

  return (
    <div className="soft-card p-5">
      <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
        Students
      </h2>
      {error && (
        <p className="mt-2 text-xs" style={{ color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}
      <div className="mt-3 divide-y" style={{ borderColor: "var(--border)" }}>
        {students.map((s, i) => {
          const hasPhone = !!s.phone.trim();
          const busy = loadingId === s.id;
          return (
            <div key={s.id} className="flex items-center gap-3 py-2.5">
              <span className="w-6 flex-none text-sm font-semibold tabular-nums" style={{ color: "var(--text-muted)" }}>
                {i + 1}.
              </span>
              <span className="flex-1 truncate text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {s.name}
              </span>
              {!hasPhone && <span className="pill">no phone</span>}
              <div className="flex flex-none items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => openWhatsApp(s)}
                  disabled={!hasPhone || busy}
                  title={hasPhone ? "Open this student's link in WhatsApp to send" : "No phone number on file"}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-white transition-opacity duration-200 disabled:opacity-40"
                  style={{ background: "#25d366" }}
                >
                  <ChatIcon size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => previewParentLink(s)}
                  disabled={busy}
                  title="Preview the link sent to parents"
                  className="flex h-8 w-8 items-center justify-center rounded-full border transition-colors duration-200 hover:bg-[var(--accent-soft)] disabled:opacity-40"
                  style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                >
                  <EyeIcon size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => openFullReport(s)}
                  title="Open this student's full report"
                  className="flex h-8 w-8 items-center justify-center rounded-full border transition-colors duration-200 hover:bg-[var(--accent-soft)]"
                  style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                >
                  <SheetIcon size={15} />
                </button>
              </div>
            </div>
          );
        })}
        {students.length === 0 && (
          <p className="py-3 text-center text-sm" style={{ color: "var(--text-muted)" }}>
            No students in this upload.
          </p>
        )}
      </div>
    </div>
  );
}
