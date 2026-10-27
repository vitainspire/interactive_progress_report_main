import { useState } from "react";
import { api } from "../api/client";
import type { DriveImportFileResult } from "../types";

/** Shown for a Drive file whose roster looks like it might already be one
 * of this account's classes (see find_duplicate_candidate on the backend)
 * — lets the teacher decide whether it's really the same class re-uploaded
 * (replace) or a genuinely different one that just happens to overlap
 * (keep separate), rather than the app silently guessing either way. */
export function DriveDuplicateResolver({ result, onResolved }: { result: DriveImportFileResult; onResolved: () => void }) {
  const [busy, setBusy] = useState<"replace" | "create_separate" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function resolve(action: "replace" | "create_separate") {
    setBusy(action);
    setError(null);
    try {
      await api.post("/batches/resolve-drive-duplicate", {
        file_id: result.file_id,
        mime_type: result.mime_type,
        file_name: result.file_name,
        folder_id: result.folder_id,
        action,
        target_batch_id: action === "replace" ? result.candidate_batch_id : undefined,
      });
      onResolved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not do that");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="rounded-lg border p-3 text-sm" style={{ borderColor: "var(--border)" }}>
      <p style={{ color: "var(--text-primary)" }}>
        <strong>{result.file_name}</strong> looks like it might be the same class as{" "}
        <strong>{result.candidate_batch_name}</strong> — {result.overlap_count} of its{" "}
        {Math.min(result.existing_student_count ?? 0, result.new_student_count ?? 0)} students match.
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => resolve("replace")}
          disabled={busy !== null}
          className="accent-fill rounded-md px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60"
        >
          {busy === "replace" ? "Replacing…" : `Replace "${result.candidate_batch_name}"`}
        </button>
        <button
          type="button"
          onClick={() => resolve("create_separate")}
          disabled={busy !== null}
          className="rounded-md border px-3 py-1.5 text-xs font-semibold disabled:opacity-60"
          style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
        >
          {busy === "create_separate" ? "Creating…" : "Keep as a new, separate class"}
        </button>
      </div>
      {error && (
        <p className="mt-1.5 text-xs" style={{ color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
