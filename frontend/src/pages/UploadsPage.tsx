import { useState } from "react";
import { TextbooksPage } from "./TextbooksPage";
import { UploadPage } from "./UploadPage";

type Tab = "sheet" | "textbooks";

/** Both of this class's upload actions (the Excel progress sheet and
 * textbook PDFs) live under one nav entry since they're both "upload
 * something for this class" — just different file types feeding different
 * parts of the app. */
export function UploadsPage() {
  const [tab, setTab] = useState<Tab>("sheet");

  return (
    <div>
      <div className="mx-auto flex max-w-2xl gap-2">
        <button
          onClick={() => setTab("sheet")}
          className="rounded-full border px-4 py-1.5 text-sm font-medium transition-colors"
          style={{
            borderColor: "var(--border)",
            color: tab === "sheet" ? "var(--accent)" : "var(--text-secondary)",
            background: tab === "sheet" ? "var(--accent-soft)" : "transparent",
          }}
        >
          Progress sheet
        </button>
        <button
          onClick={() => setTab("textbooks")}
          className="rounded-full border px-4 py-1.5 text-sm font-medium transition-colors"
          style={{
            borderColor: "var(--border)",
            color: tab === "textbooks" ? "var(--accent)" : "var(--text-secondary)",
            background: tab === "textbooks" ? "var(--accent-soft)" : "transparent",
          }}
        >
          Textbooks
        </button>
      </div>
      <div className="mt-5">{tab === "sheet" ? <UploadPage /> : <TextbooksPage />}</div>
    </div>
  );
}
