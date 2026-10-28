import { useRef, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { SchoolIcon } from "../components/Icons";

/** One place to edit everything that's stamped on a parent's report and the
 * printed substitution sheet: school name, address, and now a photo — each
 * saved independently, matching the "few steps" design this app's teacher
 * users need rather than one big form with a single submit. Reachable any
 * time from the account menu in Layout.tsx, not just at first-time setup
 * (SchoolSetupPage only collects the name, once, before this page exists
 * for an account). */
export function SchoolProfilePage() {
  const { user, setSchoolName, setSchoolAddress, setSchoolPhoto, removeSchoolPhoto } = useAuth();

  const [name, setName] = useState(user?.default_school_name ?? "");
  const [nameBusy, setNameBusy] = useState(false);
  const [nameSaved, setNameSaved] = useState(false);

  const [address, setAddress] = useState(user?.school_address ?? "");
  const [addressBusy, setAddressBusy] = useState(false);
  const [addressSaved, setAddressSaved] = useState(false);

  const [photoBusy, setPhotoBusy] = useState(false);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [photoVersion, setPhotoVersion] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function saveName() {
    setNameBusy(true);
    setNameSaved(false);
    try {
      await setSchoolName(name);
      setNameSaved(true);
    } finally {
      setNameBusy(false);
    }
  }

  async function saveAddress() {
    setAddressBusy(true);
    setAddressSaved(false);
    try {
      await setSchoolAddress(address);
      setAddressSaved(true);
    } finally {
      setAddressBusy(false);
    }
  }

  async function onPickPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setPhotoBusy(true);
    setPhotoError(null);
    try {
      await setSchoolPhoto(file);
      setPhotoVersion((v) => v + 1);
    } catch (err) {
      setPhotoError(err instanceof Error ? err.message : "Could not upload that photo");
    } finally {
      setPhotoBusy(false);
    }
  }

  async function onRemovePhoto() {
    setPhotoBusy(true);
    setPhotoError(null);
    try {
      await removeSchoolPhoto();
      setPhotoVersion((v) => v + 1);
    } finally {
      setPhotoBusy(false);
    }
  }

  return (
    <section>
      <header>
        <h1 className="text-2xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          School profile
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Shown on every parent report link, timetable, and printed substitution sheet you generate.
        </p>
      </header>

      <div className="soft-card mt-6 p-6">
        <label htmlFor="profile-school-name" className="text-xs" style={{ color: "var(--text-secondary)" }}>
          School name
        </label>
        <div className="mt-1.5 flex flex-wrap gap-2">
          <input
            id="profile-school-name"
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setNameSaved(false);
            }}
            placeholder="e.g. S.P.P High School, Gurajanapalli"
            className="min-w-64 flex-1"
          />
          <button
            type="button"
            onClick={saveName}
            disabled={nameBusy || !name.trim()}
            className="accent-fill rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {nameBusy ? "Saving…" : "Save"}
          </button>
        </div>
        {nameSaved && (
          <p className="mt-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
            Saved.
          </p>
        )}
      </div>

      <div className="soft-card mt-5 p-6">
        <label htmlFor="profile-school-address" className="text-xs" style={{ color: "var(--text-secondary)" }}>
          School address (optional)
        </label>
        <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
          Shown under the school name on the printed substitution sheet.
        </p>
        <div className="mt-1.5 flex flex-wrap gap-2">
          <input
            id="profile-school-address"
            type="text"
            value={address}
            onChange={(e) => {
              setAddress(e.target.value);
              setAddressSaved(false);
            }}
            placeholder="e.g. Gurajanapalli, Karapa Mandal, Kakinada Dt."
            className="min-w-64 flex-1"
          />
          <button
            type="button"
            onClick={saveAddress}
            disabled={addressBusy}
            className="accent-fill rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {addressBusy ? "Saving…" : "Save"}
          </button>
        </div>
        {addressSaved && (
          <p className="mt-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>
            Saved.
          </p>
        )}
      </div>

      <div className="soft-card mt-5 p-6">
        <label className="text-xs" style={{ color: "var(--text-secondary)" }}>
          School photo
        </label>
        <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
          Shown at the top of every parent's report link — a photo of your school's gate or building works well. Until
          you upload one, parents see a generic placeholder photo instead of your school.
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-4">
          <div
            className="flex h-24 w-40 items-center justify-center overflow-hidden rounded-lg border"
            style={{ borderColor: "var(--border)", background: "var(--surface-2)" }}
          >
            {user?.has_school_photo ? (
              <img
                key={photoVersion}
                src={`${api.schoolPhotoPreviewUrl()}&v=${photoVersion}`}
                alt="Your school"
                className="h-full w-full object-cover"
              />
            ) : (
              <SchoolIcon size={22} className="opacity-40" />
            )}
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={photoBusy}
                className="accent-fill rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {photoBusy ? "Uploading…" : user?.has_school_photo ? "Change photo" : "Upload photo"}
              </button>
              {user?.has_school_photo && (
                <button
                  type="button"
                  onClick={onRemovePhoto}
                  disabled={photoBusy}
                  className="rounded-md border px-4 py-2 text-sm font-semibold disabled:opacity-60"
                  style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
                >
                  Remove
                </button>
              )}
            </div>
            <input ref={fileInputRef} type="file" accept="image/*" onChange={onPickPhoto} className="hidden" />
            {photoError && (
              <p role="alert" className="text-xs" style={{ color: "var(--accent-mark)" }}>
                {photoError}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
