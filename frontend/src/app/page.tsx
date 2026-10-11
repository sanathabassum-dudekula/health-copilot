"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useTranslation } from "react-i18next";
import { LANGS, Lang } from "@/i18n";
import { api, Profile } from "@/api";
import Icon from "@/components/Icon";

export default function ChooseProfilePage() {
  const { i18n } = useTranslation();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [memberName, setMemberName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [bloodGroup, setBloodGroup] = useState("");
  const [allergies, setAllergies] = useState("");
  const [conditions, setConditions] = useState("");
  const [medicines, setMedicines] = useState("");
  const [previousRecords, setPreviousRecords] = useState("");
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api.profile()
      .then(setProfile)
      .catch(() =>
        setNotice(
          "We couldn't load your profile. Check that the health service is running."
        )
      )
      .finally(() => setLoading(false));
  }, []);

  function handleAddMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setNotice(
      "Family profiles are not connected to secure account storage yet. Your details have not been saved. We will connect this form after the family-account backend is ready."
    );
  }

  const initials = (profile?.name || "My Profile")
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="profile-chooser curamind-profile-split-layout-root mx-auto w-full max-w-6xl space-y-6 lg:py-4">
      <div className="curamind-profile-split-layout grid items-start gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-12">
        <aside className="curamind-profile-welcome flex flex-col justify-center rounded-3xl border border-line bg-white p-6 sm:p-8 lg:sticky lg:top-8 lg:min-h-[560px]">
          <Image
            src="/curamind-logo.jpeg"
            alt="CuraMind logo"
            width={520}
            height={180}
            priority
            className="mb-8 h-auto w-[180px] max-w-full object-contain sm:w-[220px]"
          />

          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-line bg-brand-soft px-3 py-1.5 text-sm font-medium text-brand">
            <Icon name="heart" className="h-4 w-4" />
            Your Health, Clearly Connected
          </span>

          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            A healthier view starts here.
          </h1>

          <p className="mt-4 text-base leading-7 text-muted">
            Keep your medical records, reports, and health history organised in
            one protected place.
          </p>

          <div className="mt-8 grid grid-cols-3 gap-3 text-center">
            <div className="rounded-2xl bg-brand-soft p-3">
              <Icon name="shield" className="mx-auto h-5 w-5 text-brand" />
              <p className="mt-2 text-xs font-semibold text-ink">Private</p>
            </div>

            <div className="rounded-2xl bg-brand-soft p-3">
              <Icon name="heart" className="mx-auto h-5 w-5 text-brand" />
              <p className="mt-2 text-xs font-semibold text-ink">Personal</p>
            </div>

            <div className="rounded-2xl bg-brand-soft p-3">
              <Icon name="activity" className="mx-auto h-5 w-5 text-brand" />
              <p className="mt-2 text-xs font-semibold text-ink">Connected</p>
            </div>
          </div>
        </aside>

        <div className="min-w-0 space-y-6">
          <header className="flex justify-end">
            <label className="flex items-center gap-2 text-sm font-medium text-[#123C46]">
              <span>Language</span>

              <select
                aria-label="Language"
                className="min-h-10 rounded-xl border border-line bg-white px-3 text-[#123C46]"
                value={i18n.language in LANGS ? i18n.language : "en"}
                onChange={(event) => {
                  const next = event.target.value as Lang;
                  i18n.changeLanguage(next);

                  try {
                    localStorage.setItem("lang", next);
                  } catch {}

                  api.setLanguage(next).catch(() => {});
                }}
              >
                {(Object.keys(LANGS) as Lang[]).map((key) => (
                  <option key={key} value={key}>
                    {LANGS[key]}
                  </option>
                ))}
              </select>
            </label>
          </header>

          <section
            className="relative overflow-hidden rounded-3xl border border-line p-6 shadow-card sm:p-9"
            style={{
              background:
                "linear-gradient(135deg, var(--brand-soft) 0%, var(--surface-2) 65%, var(--surface) 100%)",
            }}
          >
            <div className="relative max-w-2xl space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full border border-line bg-white/70 px-3 py-1.5 text-sm font-medium text-brand">
                <Icon name="heart" className="h-4 w-4" />
                Your Health, Clearly Connected
              </div>

              <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
                Choose your profile
              </h1>

              <p className="max-w-xl text-base leading-7 text-muted">
                Select whose health records you want to view. Each person
                should have a separate, protected health profile.
              </p>
            </div>
          </section>

          <section className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold">Your profiles</h2>
              <p className="mt-1 text-sm text-muted">
                Start with your personal health records.
              </p>
            </div>

            {loading ? (
              <div className="card p-6 text-sm text-muted">
                Loading your profile…
              </div>
            ) : profile ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <Link
                  href="/health"
                  className="card group flex items-start gap-4 p-5 transition hover:border-brand hover:shadow-card"
                >
                  <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-brand-soft text-lg font-semibold text-brand">
                    {initials}
                  </span>

                  <span className="min-w-0 flex-1">
                    <span className="block text-lg font-semibold">
                      {profile.name || "My Profile"}
                    </span>

                    <span className="mt-1 block text-sm text-muted">
                      My health records
                    </span>

                    <span className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-brand">
                      Continue to records
                      <Icon name="chevron" className="h-4 w-4" />
                    </span>
                  </span>
                </Link>

                <Link
                  href="/profile"
                  className="card flex items-start gap-4 p-5 transition hover:border-brand"
                >
                  <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-surface-2 text-brand">
                    <Icon name="user" className="h-6 w-6" />
                  </span>

                  <span>
                    <span className="block font-semibold">
                      Profile settings
                    </span>

                    <span className="mt-1 block text-sm leading-6 text-muted">
                      Update personal details, language, and ABHA information.
                    </span>

                    <span className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-brand">
                      Manage profile
                      <Icon name="chevron" className="h-4 w-4" />
                    </span>
                  </span>
                </Link>
              </div>
            ) : (
              <div className="card p-5 text-sm text-muted">
                Your profile could not be loaded. Please check the backend
                connection and refresh this page.
              </div>
            )}
          </section>
        </div>
      </div>

      <section className="card curamind-family-section space-y-4 p-5 sm:p-6">
        <div className="flex items-start gap-3">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-brand-soft text-brand">
            <Icon name="user" className="h-6 w-6" />
          </span>

          <div className="flex-1">
            <h2 className="text-xl font-semibold">Family profiles</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              Keep each family member’s health history separate and protected.
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-dashed border-line p-4">
          <p className="font-medium">No linked family profiles yet</p>
          <p className="mt-1 text-sm leading-6 text-muted">
            Add a family member after secure account linking is available. A
            phone number alone will not grant access to anyone’s medical
            records.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setShowAdd((value) => !value);
            setNotice("");
          }}
        >
          <Icon name="plus" className="h-4 w-4" />
          {showAdd ? "Close form" : "Add family member"}
        </button>

        {showAdd && (
          <form
            onSubmit={handleAddMember}
            className="space-y-5 border-t border-line pt-5"
          >
            <h3 className="font-semibold">Family member details</h3>

            <p className="text-sm leading-6 text-muted">
              Preview only. These details are not saved until secure
              family-account storage is implemented.
            </p>

            <div>
              <h4 className="text-sm font-semibold">Basic information</h4>

              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <label className="block space-y-1.5 text-sm font-medium">
                  Full name *
                  <input
                    required
                    value={memberName}
                    onChange={(event) => setMemberName(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                    placeholder="Enter full name"
                  />
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  Date of birth
                  <input
                    type="date"
                    value={dateOfBirth}
                    onChange={(event) => setDateOfBirth(event.target.value)}
                    max={new Date().toISOString().slice(0, 10)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                  />
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  Age (optional if date of birth is entered)
                  <input
                    type="number"
                    min="0"
                    max="125"
                    value={age}
                    onChange={(event) => setAge(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                    placeholder="Age in years"
                  />
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  Gender
                  <select
                    value={gender}
                    onChange={(event) => setGender(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                  >
                    <option value="">Select gender (optional)</option>
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="other">Other</option>
                    <option value="prefer_not_to_say">
                      Prefer not to say
                    </option>
                  </select>
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  Blood type
                  <select
                    value={bloodGroup}
                    onChange={(event) => setBloodGroup(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                  >
                    <option value="">Unknown / not provided</option>
                    {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(
                      (item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      )
                    )}
                  </select>
                </label>
              </div>
            </div>

            <div className="space-y-4 border-t border-line pt-4">
              <h4 className="text-sm font-semibold">Medical information</h4>

              <label className="block space-y-1.5 text-sm font-medium">
                Allergies
                <textarea
                  value={allergies}
                  onChange={(event) => setAllergies(event.target.value)}
                  rows={2}
                  maxLength={2000}
                  className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-ink"
                  placeholder="Known allergies or reactions"
                />
              </label>

              <label className="block space-y-1.5 text-sm font-medium">
                Existing conditions and medical history
                <textarea
                  value={conditions}
                  onChange={(event) => setConditions(event.target.value)}
                  rows={3}
                  maxLength={4000}
                  className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-ink"
                  placeholder="Conditions, surgeries, fractures, or other relevant history"
                />
              </label>

              <label className="block space-y-1.5 text-sm font-medium">
                Current medicines and dosages
                <textarea
                  value={medicines}
                  onChange={(event) => setMedicines(event.target.value)}
                  rows={2}
                  maxLength={3000}
                  className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-ink"
                  placeholder="Medicine names, dosages, and frequency if known"
                />
              </label>

              <label className="block space-y-1.5 text-sm font-medium">
                Previous medical records
                <textarea
                  value={previousRecords}
                  onChange={(event) => setPreviousRecords(event.target.value)}
                  rows={3}
                  maxLength={4000}
                  className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-ink"
                  placeholder="Previous reports, prescriptions, diagnoses, or record notes"
                />
              </label>
            </div>

            <div className="rounded-2xl border border-line bg-brand-soft p-4">
              <h4 className="font-semibold">Emergency contact (optional)</h4>
              <p className="mt-1 text-sm text-muted">
                Both fields can be left blank.
              </p>

              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <label className="block space-y-1.5 text-sm font-medium">
                  Contact name
                  <input
                    value={emergencyName}
                    onChange={(event) => setEmergencyName(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-white px-3 text-ink"
                    placeholder="Emergency contact name"
                  />
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  Contact phone number
                  <input
                    type="tel"
                    value={emergencyPhone}
                    onChange={(event) => setEmergencyPhone(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-white px-3 text-ink"
                    placeholder="Optional phone number"
                  />
                </label>
              </div>
            </div>

            <p className="text-xs leading-5 text-muted">
              * Required fields. Family details are not saved yet. ABHA access
              requires secure identity verification and permission.
            </p>

            <button type="submit" className="btn btn-primary">
              Review setup requirements
            </button>
          </form>
        )}

        {notice && (
          <p
            role="status"
            className="rounded-xl border border-line bg-surface-2 p-3 text-sm leading-6 text-muted"
          >
            {notice}
          </p>
        )}
      </section>

      <p className="text-center text-xs leading-5 text-muted">
        Family access and cross-device syncing require secure account
        verification and permission controls.
      </p>
    </div>
  );
}