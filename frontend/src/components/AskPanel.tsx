import { useCallback, useState } from "react";
import { api } from "../api/client";
import { SimpleBarChart, SimpleLineChart } from "./Charts";
import { DataTable } from "./DataTable";
import { MicIcon, SpeakerIcon, StopIcon } from "./Icons";
import { useSpeechRecognition, useSpeechSynthesis } from "../hooks/useVoice";
import type { QueryResponse } from "../types";

const EXAMPLES = [
  "How did Section B do in SA-1 Maths?",
  "Tell me about Gowthu Abhishek Kumar",
  "Top 5 students in FA-2",
  "Who failed in Biology?",
  "What is Abhishek Kumar's attendance?",
  "Compare Section A and Section B in SA-1",
];

interface HistoryItem {
  question: string;
  response: QueryResponse;
}

/** The full "ask anything about the class" feature — input, voice, examples,
 * and answer history with charts/tables. Used standalone inside the floating
 * widget (see FloatingAskButton), with no page-level heading or margins of
 * its own so it fits in a compact panel. */
export function AskPanel({ classId }: { classId: number }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const { speak, stop, speaking, supported: ttsSupported } = useSpeechSynthesis();

  const ask = useCallback(
    async (q: string) => {
      const trimmed = q.trim();
      if (!trimmed) return;
      setLoading(true);
      try {
        const res = await api.post<QueryResponse>(`/query?class_id=${classId}`, { question: trimmed });
        setHistory((h) => [{ question: trimmed, response: res }, ...h]);
        setQuestion("");
      } finally {
        setLoading(false);
      }
    },
    [classId],
  );

  const onFinalTranscript = useCallback(
    (text: string) => {
      setQuestion(text);
      ask(text);
    },
    [ask],
  );
  const { listening, interim, supported: sttSupported, start, stop: stopListening } = useSpeechRecognition(onFinalTranscript);

  return (
    <div>
      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
        Questions are matched with pattern-based rules, not an AI model — try an example below.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="mt-3 flex gap-2"
      >
        <input
          value={listening ? interim || question : question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. How did Section B do in SA-1 Maths?"
          className="flex-1 rounded-xl border px-3 py-2 text-sm shadow-sm"
          style={{ borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-primary)" }}
        />
        {sttSupported && (
          <button
            type="button"
            onClick={() => (listening ? stopListening() : start())}
            className="shrink-0 rounded-full border px-3 py-2 text-sm shadow-sm"
            style={{ borderColor: "var(--border)", color: listening ? "var(--status-critical)" : "var(--text-primary)", background: "var(--surface-1)" }}
            title="Ask by voice"
          >
            {listening ? <StopIcon size={15} /> : <MicIcon size={15} />}
          </button>
        )}
        <button
          type="submit"
          disabled={loading}
          className="gradient-fill shrink-0 rounded-full px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:opacity-50"
        >
          Ask
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => ask(ex)}
            className="rounded-full border px-2.5 py-1 text-xs transition-colors hover:bg-[var(--accent-soft)]"
            style={{ borderColor: "var(--border)", color: "var(--text-secondary)", background: "var(--surface-1)" }}
          >
            {ex}
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-3">
        {history.map((item, i) => (
          <div key={i} className="soft-card p-4">
            <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
              {item.question}
            </p>
            <div className="mt-1 flex items-start justify-between gap-3">
              <p className="text-sm" style={{ color: "var(--text-primary)" }}>
                {item.response.answer}
              </p>
              {ttsSupported && (
                <button
                  onClick={() => (speaking ? stop() : speak(item.response.answer))}
                  className="shrink-0"
                  style={{ color: "var(--accent)" }}
                  title="Read aloud"
                >
                  {speaking ? <StopIcon size={16} /> : <SpeakerIcon size={16} />}
                </button>
              )}
            </div>
            {item.response.chart && (
              <div className="mt-3">
                {item.response.chart.type === "line" ? (
                  <SimpleLineChart data={item.response.chart.data} height={180} />
                ) : (
                  <SimpleBarChart data={item.response.chart.data} height={180} />
                )}
              </div>
            )}
            {item.response.table && (
              <div className="mt-3">
                <DataTable columns={item.response.table.columns} rows={item.response.table.rows} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
