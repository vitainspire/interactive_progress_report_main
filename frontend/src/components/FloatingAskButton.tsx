import { useState } from "react";
import { AskPanel } from "./AskPanel";
import { ChatIcon, CloseIcon } from "./Icons";

/** A chat-widget-style entry point for "Ask anything about the class" — a
 * floating button in the bottom-right corner that opens a panel with the
 * exact same input/voice/examples/history as the old dedicated page. */
export function FloatingAskButton({ classId }: { classId: number }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      {open && (
        <div
          className="soft-card fixed bottom-24 right-6 z-50 flex max-h-[75vh] w-[23rem] max-w-[calc(100vw-3rem)] flex-col overflow-hidden md:max-h-[85vh] md:w-[34rem] lg:w-[40rem]"
          role="dialog"
          aria-label="Ask anything about the class"
        >
          <div className="flex items-center justify-between px-5 pb-3 pt-4" style={{ borderBottom: "1px solid var(--border)" }}>
            <h2 className="font-display text-base font-bold" style={{ color: "var(--text-primary)" }}>
              Ask anything about the class
            </h2>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-colors hover:bg-[var(--accent-soft)]"
              style={{ color: "var(--text-secondary)" }}
            >
              <CloseIcon size={16} />
            </button>
          </div>
          <div className="overflow-y-auto px-5 py-4">
            <AskPanel classId={classId} />
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close ask panel" : "Ask anything about the class"}
        title="Ask anything about the class"
        className="gradient-fill fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full text-white shadow-lg transition-transform hover:scale-105"
      >
        {open ? <CloseIcon size={22} /> : <ChatIcon size={22} />}
      </button>
    </>
  );
}
