/**
 * Browse-and-pick a Google Sheet straight from the teacher's own Drive,
 * entirely client-side: our backend never sees the teacher's Google
 * credentials or touches Google's APIs at all. Once a file is picked, its
 * bytes are downloaded in the browser (using the teacher's own short-lived
 * access token) and handed back as a plain File object — from that point
 * on it flows through the exact same /batches/upload endpoint as a file
 * picked from local disk, so the backend needs zero changes for this.
 *
 * Scope used: drive.file — this app can only ever see files the teacher
 * explicitly selects in the picker dialog below, never their whole Drive.
 */

declare global {
  interface Window {
    google: any;
    gapi: any;
  }
}

const SCOPE = "https://www.googleapis.com/auth/drive.file";

let scriptsReadyPromise: Promise<void> | null = null;
let tokenClient: any = null;
let cachedAccessToken: string | null = null;

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Could not load ${src}`));
    document.body.appendChild(script);
  });
}

/** Call this as early as possible (e.g. on page mount) so the scripts are
 * already warm by the time the teacher clicks the button — Google's token
 * popup is more reliable the less async work happens between the click and
 * requesting the token. */
export function preloadGooglePicker(): Promise<void> {
  if (!scriptsReadyPromise) {
    scriptsReadyPromise = (async () => {
      await Promise.all([loadScript("https://accounts.google.com/gsi/client"), loadScript("https://apis.google.com/js/api.js")]);
      await new Promise<void>((resolve) => window.gapi.load("picker", () => resolve()));
    })();
  }
  return scriptsReadyPromise;
}

function requestAccessToken(clientId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!tokenClient) {
      tokenClient = window.google.accounts.oauth2.initTokenClient({
        client_id: clientId,
        scope: SCOPE,
        callback: () => {},
      });
    }
    tokenClient.callback = (resp: { error?: string; access_token?: string }) => {
      if (resp.error || !resp.access_token) {
        reject(new Error(resp.error || "Google did not return an access token"));
        return;
      }
      cachedAccessToken = resp.access_token;
      resolve(resp.access_token);
    };
    tokenClient.requestAccessToken({ prompt: cachedAccessToken ? "" : "consent" });
  });
}

interface PickedDoc {
  id: string;
  name: string;
  mimeType: string;
}

function openPicker(apiKey: string, clientId: string, token: string): Promise<PickedDoc | null> {
  return new Promise((resolve) => {
    // With the narrow drive.file scope, picking a file doesn't by itself
    // grant the token API access to it — Picker only does that handoff
    // when it knows which Cloud project is asking, via setAppId(). The
    // project number is the numeric prefix on every OAuth Client ID
    // (e.g. "138403234482-xxxx.apps.googleusercontent.com"), so it can be
    // pulled straight from the Client ID instead of asking for it separately.
    const appId = clientId.split("-")[0];
    const view = new window.google.picker.DocsView(window.google.picker.ViewId.SPREADSHEETS).setIncludeFolders(true);
    const picker = new window.google.picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(token)
      .setDeveloperKey(apiKey)
      .setAppId(appId)
      .setOrigin(window.location.protocol + "//" + window.location.host)
      .setCallback((data: { action: string; docs?: PickedDoc[] }) => {
        if (data.action === window.google.picker.Action.PICKED && data.docs && data.docs[0]) {
          const doc = data.docs[0];
          resolve({ id: doc.id, name: doc.name, mimeType: doc.mimeType });
        } else if (data.action === window.google.picker.Action.CANCEL) {
          resolve(null);
        }
      })
      .build();
    picker.setVisible(true);
  });
}

async function downloadPickedFile(doc: PickedDoc, token: string): Promise<Blob> {
  const isNativeGoogleSheet = doc.mimeType === "application/vnd.google-apps.spreadsheet";
  const url = isNativeGoogleSheet
    ? `https://www.googleapis.com/drive/v3/files/${doc.id}/export?mimeType=${encodeURIComponent("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}&supportsAllDrives=true`
    : `https://www.googleapis.com/drive/v3/files/${doc.id}?alt=media&supportsAllDrives=true`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Could not download the selected file from Drive (HTTP ${res.status}). ${body.slice(0, 200)}`);
  }
  return res.blob();
}

/** Opens Google's account chooser (if needed), then a Drive picker scoped
 * to spreadsheets, and returns the picked file as a plain .xlsx File —
 * or null if the teacher cancelled. */
export async function pickGoogleSheet(clientId: string, apiKey: string): Promise<File | null> {
  await preloadGooglePicker();
  const token = await requestAccessToken(clientId);
  const doc = await openPicker(apiKey, clientId, token);
  if (!doc) return null;
  const blob = await downloadPickedFile(doc, token);
  const filename = doc.name.toLowerCase().endsWith(".xlsx") ? doc.name : `${doc.name}.xlsx`;
  return new File([blob], filename, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
}

export function isGooglePickerConfigured(): boolean {
  return Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID && import.meta.env.VITE_GOOGLE_API_KEY);
}
