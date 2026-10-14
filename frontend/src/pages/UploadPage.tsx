import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";

interface UploadResult {
  filename: string;
  student_count: number;
  phases: string[];
  sections: string[];
  staff_entries: number;
}

export function UploadPage() {
  const { user } = useAuth();
  const classId = Number(useParams().classId);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  async function handleFile(file: File) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.upload<UploadResult>(`/upload?class_id=${classId}`, file);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  if (user?.is_demo) {
    return (
      <div className="soft-card mx-auto max-w-2xl p-6 text-sm">
        <p className="font-semibold" style={{ color: "var(--accent-gold)" }}>
          Uploading is disabled on the shared demo account.
        </p>
        <p className="mt-1" style={{ color: "var(--text-secondary)" }}>
          Create your own free account to upload your school's own progress sheet — your data stays private to you.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
        Upload progress sheet
      </h1>
      <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
        Upload the school's .xlsx progress-tracking workbook. This replaces the currently loaded dataset.
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
        onClick={() => inputRef.current?.click()}
        className="soft-card mt-6 flex cursor-pointer flex-col items-center justify-center p-14 text-center transition"
        style={{ borderWidth: 2, borderStyle: "dashed", borderColor: dragOver ? "var(--accent)" : "var(--border)" }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xlsm"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
        <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
          Drop the .xlsx file here, or click to browse
        </p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
          .xlsx / .xlsm only
        </p>
      </div>

      {loading && (
        <p className="mt-4 text-sm" style={{ color: "var(--text-secondary)" }}>
          Parsing workbook…
        </p>
      )}
      {error && (
        <p className="mt-4 rounded-xl p-3 text-sm" style={{ background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}
      {result && (
        <div className="soft-card mt-4 p-5 text-sm">
          <p className="font-semibold" style={{ color: "var(--status-good)" }}>
            ✓ Loaded {result.student_count} students from {result.filename}
          </p>
          <p className="mt-1" style={{ color: "var(--text-secondary)" }}>
            Sections: {result.sections.join(", ")} · Exam phases: {result.phases.join(", ")} · Staff entries: {result.staff_entries}
          </p>
          <button
            onClick={() => navigate(`/c/${classId}`)}
            className="gradient-fill mt-3 rounded-full px-4 py-2 text-sm font-semibold text-white shadow-sm"
          >
            Go to dashboard
          </button>
        </div>
      )}
    </div>
  );
}
