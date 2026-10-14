import { useEffect, useState } from "react";
import { api } from "../api/client";

interface IntegrationStatus {
  whatsapp_configured: boolean;
  whatsapp_template_name: string;
  whatsapp_template_lang: string;
  sms_configured: boolean;
}

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span
      className="rounded-full px-2.5 py-1 text-xs font-semibold"
      style={ok ? { background: "var(--status-good-soft)", color: "var(--status-good)" } : { background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}
    >
      {ok ? "Configured" : "Not configured"}
    </span>
  );
}

export function IntegrationsPage() {
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phone, setPhone] = useState("");
  const [channel, setChannel] = useState<"whatsapp" | "sms">("whatsapp");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);

  function loadStatus() {
    api
      .get<IntegrationStatus>("/integrations/status")
      .then(setStatus)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load integration status"));
  }

  useEffect(loadStatus, []);

  async function sendTest(e: React.FormEvent) {
    e.preventDefault();
    setSending(true);
    setResult(null);
    try {
      await api.post("/integrations/test-send", { phone: phone.trim(), channel });
      setResult({ ok: true, message: `Test message sent via ${channel === "whatsapp" ? "WhatsApp" : "SMS"} — check that phone.` });
    } catch (err) {
      setResult({ ok: false, message: err instanceof Error ? err.message : "Send failed" });
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          WhatsApp / SMS setup
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          These are configured on the server itself (environment variables), not here — this page just shows current
          status and lets you fire a real test message once credentials are in place.
        </p>
      </div>

      {error && <p className="text-sm" style={{ color: "var(--accent-mark)" }}>{error}</p>}

      {status && (
        <div className="soft-card space-y-3 p-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>WhatsApp Cloud API</div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                Template: {status.whatsapp_template_name} ({status.whatsapp_template_lang})
              </div>
            </div>
            <StatusBadge ok={status.whatsapp_configured} />
          </div>
          <div className="flex items-center justify-between border-t pt-3" style={{ borderColor: "var(--border)" }}>
            <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>SMS (Twilio)</div>
            <StatusBadge ok={status.sms_configured} />
          </div>
        </div>
      )}

      <form onSubmit={sendTest} className="soft-card space-y-3 p-5">
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          Send a test message
        </h2>
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Sends one real message to a phone number of your choice using placeholder data — no student or batch
          involved. Use this the moment credentials are set, to confirm everything actually works end to end.
        </p>
        <div className="flex gap-2">
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value as "whatsapp" | "sms")}
            className="rounded-full border px-3 py-2 text-sm"
            style={{ borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" }}
          >
            <option value="whatsapp">WhatsApp</option>
            <option value="sms">SMS</option>
          </select>
          <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone number, e.g. 9876543210" />
        </div>
        {result && (
          <p
            className="rounded-lg p-3 text-sm"
            style={result.ok ? { background: "var(--status-good-soft)", color: "var(--status-good)" } : { background: "var(--accent-mark-soft)", color: "var(--accent-mark)" }}
          >
            {result.message}
          </p>
        )}
        <button
          type="submit"
          disabled={sending || !phone.trim()}
          className="gradient-fill rounded-full px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
        >
          {sending ? "Sending…" : "Send test message"}
        </button>
      </form>
    </div>
  );
}
