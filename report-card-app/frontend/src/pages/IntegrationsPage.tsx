import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { WhatsappChannelMode, WhatsappLanguage } from "../types";

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

const selectStyle = { borderColor: "var(--border)", background: "var(--page-plane)", color: "var(--text-primary)" };

/** The WhatsApp Business phone number/token/template name are one shared
 * credential for this whole app (set server-side) — but which approved
 * template language to send in, whether to fall back to SMS at all, and
 * which country code a bare 10-digit number gets, are each school's own
 * choice. Saved to this account, not this batch, since every batch a
 * school uploads should message parents the same way. */
function MessageSettingsCard({ onSaved }: { onSaved: () => void }) {
  const { user, setWhatsappSettings } = useAuth();
  const [language, setLanguage] = useState<WhatsappLanguage>(user?.whatsapp_language ?? "te");
  const [channelMode, setChannelMode] = useState<WhatsappChannelMode>(user?.whatsapp_channel_mode ?? "whatsapp_then_sms");
  const [countryCode, setCountryCode] = useState(user?.default_country_code ?? "91");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await setWhatsappSettings({ whatsapp_language: language, whatsapp_channel_mode: channelMode, default_country_code: countryCode });
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save these settings");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="soft-card space-y-4 p-5">
      <div>
        <h2 className="text-base font-semibold" style={{ color: "var(--text-primary)" }}>
          Message settings
        </h2>
        <p className="mt-1 text-xs" style={{ color: "var(--text-secondary)" }}>
          Your own choices for how report links are sent to parents — the WhatsApp number/template itself is shared
          across every school on this app, but these three are yours.
        </p>
      </div>

      <div>
        <label className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
          Report language
        </label>
        <select
          value={language}
          onChange={(e) => {
            setLanguage(e.target.value as WhatsappLanguage);
            setSaved(false);
          }}
          className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
          style={selectStyle}
        >
          <option value="te">Telugu</option>
          <option value="en_US">English</option>
        </select>
      </div>

      <div>
        <label className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
          Sending channel
        </label>
        <select
          value={channelMode}
          onChange={(e) => {
            setChannelMode(e.target.value as WhatsappChannelMode);
            setSaved(false);
          }}
          className="mt-1 block w-full rounded-md border px-3 py-2 text-sm"
          style={selectStyle}
        >
          <option value="whatsapp_then_sms">WhatsApp, then SMS if it fails</option>
          <option value="whatsapp_only">WhatsApp only</option>
          <option value="sms_only">SMS only</option>
        </select>
        {channelMode !== "whatsapp_then_sms" && (
          <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
            {channelMode === "whatsapp_only"
              ? "SMS never gets tried, even if WhatsApp fails — a student with no WhatsApp delivery just won't be messaged."
              : "WhatsApp never gets tried — useful if your parents mostly don't have WhatsApp, or to avoid WhatsApp costs entirely."}
          </p>
        )}
      </div>

      <div>
        <label htmlFor="integrations-country-code" className="text-xs font-semibold" style={{ color: "var(--text-secondary)" }}>
          Default country code
        </label>
        <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
          Used when a sheet's phone number is a bare 10-digit number with no country code.
        </p>
        <div className="mt-1 flex items-center gap-1.5">
          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
            +
          </span>
          <input
            id="integrations-country-code"
            type="text"
            inputMode="numeric"
            value={countryCode}
            onChange={(e) => {
              setCountryCode(e.target.value);
              setSaved(false);
            }}
            placeholder="91"
            className="w-20"
          />
        </div>
      </div>

      {error && (
        <p role="alert" className="text-xs" style={{ color: "var(--accent-mark)" }}>
          {error}
        </p>
      )}
      {saved && (
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
          Saved.
        </p>
      )}

      <button
        type="button"
        onClick={save}
        disabled={busy}
        className="accent-fill rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
      >
        {busy ? "Saving…" : "Save settings"}
      </button>
    </div>
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
          The WhatsApp number and access token are set up on the server itself, shared across every school using this
          app — this page shows their status and lets you fire a real test message. The language, channel, and
          country code below are your own school's settings.
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

      <MessageSettingsCard onSaved={loadStatus} />

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
