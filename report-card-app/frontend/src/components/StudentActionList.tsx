import { useState } from "react";
import { api } from "../api/client";
import { ChatIcon, DotsIcon, EyeIcon, SheetIcon, SmsIcon } from "./Icons";
import type { StudentBrief } from "../types";

interface StudentLink {
  report_url: string;
  whatsapp_phone: string | null;
}

/** One row per student with four actions, replacing the old default view
 * of every selected student's full report concatenated into one long
 * iframe. Each action opens in a new tab so working down a long list of
 * students doesn't lose your place. Below the `sm` breakpoint the four
 * buttons (plus the "no phone" pill) collapse into a single "⋮" menu —
 * inline at phone widths they squeezed the name column down to a single
 * truncated letter, same disclosure pattern as DashboardPage's card menu:
 *   - WhatsApp: opens a wa.me click-to-chat link pre-filled with that
 *     student's private report link — this app never sends WhatsApp
 *     messages itself (no Cloud API configured here), it just hands the
 *     teacher's own WhatsApp a ready-to-send message. Works even when no
 *     phone number is on file: wa.me with no number opens WhatsApp's own
 *     contact picker (on the phone this app is actually used from) so the
 *     teacher can pick anyone to forward it to, not just a saved parent.
 *   - SMS: same idea via the device's own sms: URI instead of WhatsApp,
 *     for a parent without a smartphone/WhatsApp. Unlike wa.me, most SMS
 *     apps don't reliably open a contact picker with no number attached,
 *     so this one stays disabled when there's no phone on file rather than
 *     promising a fallback that may not actually work.
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
    if (!link) return;
    const message = `${student.name} గారి ప్రోగ్రెస్ రిపోర్ట్ ఇక్కడ చూడండి: ${link.report_url}`;
    const phonePart = link.whatsapp_phone ? link.whatsapp_phone : "";
    window.open(`https://wa.me/${phonePart}?text=${encodeURIComponent(message)}`, "_blank", "noopener");
  }

  async function openSms(student: StudentBrief) {
    const link = await fetchLink(student.id);
    if (!link || !link.whatsapp_phone) return;
    const message = `${student.name} గారి ప్రోగ్రెస్ రిపోర్ట్ ఇక్కడ చూడండి: ${link.report_url}`;
    window.open(`sms:+${link.whatsapp_phone}?body=${encodeURIComponent(message)}`, "_blank", "noopener");
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

              {/* Wide screens: every action inline, same as before. */}
              <div className="hidden flex-none items-center gap-1.5 sm:flex">
                {!hasPhone && <span className="pill">no phone</span>}
                <button
                  type="button"
                  onClick={() => openWhatsApp(s)}
                  disabled={busy}
                  title={hasPhone ? "Open this student's link in WhatsApp to send" : "Open in WhatsApp and choose who to send it to"}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-white transition-opacity duration-200 disabled:opacity-40"
                  style={{ background: "#25d366" }}
                >
                  <ChatIcon size={15} />
                </button>
                <button
                  type="button"
                  onClick={() => openSms(s)}
                  disabled={!hasPhone || busy}
                  title={hasPhone ? "Open this student's link in SMS to send" : "No phone number on file"}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-white transition-opacity duration-200 disabled:opacity-40"
                  style={{ background: "var(--text-secondary)" }}
                >
                  <SmsIcon size={15} />
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

              {/* Narrow screens: same four actions, collapsed behind a menu
               * so the student's name has room to actually show. */}
              <details className="relative flex-none sm:hidden">
                <summary
                  aria-label="Student actions"
                  className="flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-soft)]"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <DotsIcon size={16} />
                </summary>
                <div className="soft-card absolute right-0 z-10 mt-1 w-48 overflow-hidden p-1" style={{ boxShadow: "var(--shadow-pop)" }}>
                  {!hasPhone && (
                    <div className="px-2.5 py-1.5 text-xs font-medium" style={{ color: "var(--text-muted)" }}>
                      No phone number on file
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => openWhatsApp(s)}
                    disabled={busy}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)] disabled:opacity-40"
                    style={{ color: "var(--text-primary)" }}
                  >
                    <ChatIcon size={14} className="text-[#25d366]" />
                    WhatsApp
                  </button>
                  <button
                    type="button"
                    onClick={() => openSms(s)}
                    disabled={!hasPhone || busy}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)] disabled:opacity-40"
                    style={{ color: "var(--text-primary)" }}
                  >
                    <SmsIcon size={14} />
                    SMS
                  </button>
                  <button
                    type="button"
                    onClick={() => previewParentLink(s)}
                    disabled={busy}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)] disabled:opacity-40"
                    style={{ color: "var(--text-primary)" }}
                  >
                    <EyeIcon size={14} />
                    Preview parent link
                  </button>
                  <button
                    type="button"
                    onClick={() => openFullReport(s)}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm font-medium transition-colors duration-200 hover:bg-[var(--accent-soft)]"
                    style={{ color: "var(--text-primary)" }}
                  >
                    <SheetIcon size={14} />
                    Full report
                  </button>
                </div>
              </details>
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
