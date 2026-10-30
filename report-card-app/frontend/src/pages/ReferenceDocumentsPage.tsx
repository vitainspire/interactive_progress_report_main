import { useEffect, useState } from "react";
import { api } from "../api/client";
import { DocumentIcon } from "../components/Icons";
import { ReferenceDocumentReview } from "../components/ReferenceDocumentReview";
import type { ReferenceDocument } from "../types";

/** Reviewing an uploaded syllabus/exam-blueprint document is something a
 * teacher opens on purpose (from the account menu), not something shown to
 * them the moment they log in or finish a Drive-folder import — a folder
 * can easily produce a dozen-plus of these, and dumping them all open and
 * editable onto the Dashboard or Upload page drowned out everything else
 * on screen. Upload/Dashboard just mention a count in passing; this page
 * is the one place the actual review form lives. */
export function ReferenceDocumentsPage() {
  const [docs, setDocs] = useState<ReferenceDocument[] | null>(null);

  function refresh() {
    Promise.all([
      api.get<ReferenceDocument[]>("/reference-documents?status=pending"),
      api.get<ReferenceDocument[]>("/reference-documents?status=failed"),
    ])
      .then(([pending, failed]) => setDocs([...pending, ...failed]))
      .catch(() => setDocs([]));
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section>
      <header
        className="dot-grid-plane-dark relative overflow-hidden rounded-2xl px-6 py-6 sm:px-8 sm:py-7"
        style={{ background: "var(--accent-strong)" }}
      >
        <h1 className="font-serif text-2xl font-medium text-white sm:text-3xl">Syllabus/blueprint review</h1>
      </header>

      {docs === null && (
        <p className="mt-5 text-sm" style={{ color: "var(--text-secondary)" }}>
          Loading…
        </p>
      )}

      {docs && docs.length === 0 && (
        <div className="soft-card mt-5 flex flex-col items-center p-10 text-center" style={{ borderTop: "3px solid var(--accent)" }}>
          <span
            className="flex h-14 w-14 items-center justify-center rounded-2xl"
            style={{ background: "var(--accent-soft)", color: "var(--accent)" }}
          >
            <DocumentIcon size={24} />
          </span>
          <p className="mt-3 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
            Nothing waiting for review
          </p>
          <p className="mx-auto mt-1 max-w-sm text-sm" style={{ color: "var(--text-secondary)" }}>
            When you add a syllabus or exam-blueprint document to your Drive folder, it'll show up here once it's
            been read.
          </p>
        </div>
      )}

      {docs && docs.length > 0 && (
        <div className="mt-5 space-y-3">
          {docs.map((doc) => (
            <ReferenceDocumentReview key={doc.id} doc={doc} onChanged={refresh} />
          ))}
        </div>
      )}
    </section>
  );
}
