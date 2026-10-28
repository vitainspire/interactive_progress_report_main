import { useRef, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { CameraIcon, SchoolIcon } from "../components/Icons";

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
      <div className="flex flex-col items-center gap-2 text-center">
        <div className="relative">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={photoBusy}
            className="flex h-28 w-28 items-center justify-center overflow-hidden rounded-full border disabled:opacity-60"
            style={{ borderColor: "var(--border)", background: "var(--surface-2)", boxShadow: "var(--shadow-pop)" }}
          >
            {user?.has_school_photo ? (
              <img
                key={photoVersion}
                src={`${api.schoolPhotoPreviewUrl()}&v=${photoVersion}`}
                alt="Your school"
                className="h-full w-full object-cover"
              />
            ) : (
              <SchoolIcon size={32} className="opacity-40" />
            )}
          </button>
          <span
            className="pointer-events-none absolute bottom-0 right-0 flex h-8 w-8 items-center justify-center rounded-full border-2"
            style={{ background: "var(--accent)", borderColor: "var(--surface-1)", color: "#fff" }}
          >
            <CameraIcon size={14} />
          </span>
          <input ref={fileInputRef} type="file" accept="image/*" onChange={onPickPhoto} className="hidden" />
        </div>
        <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
          {photoBusy ? "Uploading…" : user?.has_school_photo ? "Tap to change" : "Tap to add your school's photo"}
        </p>
        {user?.has_school_photo && !photoBusy && (
          <button
            type="button"
            onClick={onRemovePhoto}
            className="text-xs font-semibold underline underline-offset-2"
            style={{ color: "var(--text-muted)" }}
          >
            Remove photo
          </button>
        )}
        {photoError && (
          <p role="alert" className="text-xs" style={{ color: "var(--accent-mark)" }}>
            {photoError}
          </p>
        )}
      </div>

      <header className="mt-6">
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

    </section>
  );
}
