"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useTranslation } from "react-i18next";
import { LANGS, Lang } from "@/i18n";
import { api, Profile, familyApi, FamilyMember } from "@/api";
import Icon from "@/components/Icon";

export default function ChooseProfilePage() {
  const { t, i18n } = useTranslation();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [memberName, setMemberName] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState("");
  const [bloodGroup, setBloodGroup] = useState("");
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [notice, setNotice] = useState("");
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [savingMember, setSavingMember] = useState(false);

  async function loadFamilyMembers() {
    try {
      const result = await familyApi.list();
      setFamilyMembers(result.members);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not load family profiles.");
    }
  }

  useEffect(() => {
    api.profile()
      .then(setProfile)
      .catch(() => setNotice(t("home.loadError")))
      .finally(() => setLoading(false));

    void loadFamilyMembers();
  }, []);

  async function handleAddMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!memberName.trim()) {
      setNotice("Please enter the family member's name.");
      return;
    }

    setSavingMember(true);
    setNotice("");

    try {
            await familyApi.add({
        name: memberName.trim(),
        ...(dateOfBirth ? { dob: dateOfBirth } : {}),
        ...(gender ? { sex: gender } : {}),
        ...(age.trim() && Number.isFinite(Number(age))
          ? { age: Number(age) }
          : {}),
        ...(bloodGroup.trim() ? { blood_group: bloodGroup.trim() } : {}),
        ...(emergencyName.trim()
          ? { emergency_contact_name: emergencyName.trim() }
          : {}),
        ...(emergencyPhone.trim()
          ? { emergency_contact_phone: emergencyPhone.trim() }
          : {}),
      });

      await loadFamilyMembers();

      setMemberName("");
      setDateOfBirth("");
      setAge("");
      setGender("");
      setBloodGroup("");
      setEmergencyName("");
      setEmergencyPhone("");

      setNotice("Family profile saved. Name, date of birth and gender were sent to the backend.");
      setShowAdd(false);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not save the family profile.");
    } finally {
      setSavingMember(false);
    }
  }
  const initials = (profile?.name || t("home.myProfile"))
    .split(/\s+/)
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="profile-chooser curamind-profile-split-layout-root mx-auto w-full max-w-6xl space-y-6 lg:py-4">
      <div className="curamind-profile-split-layout grid items-start gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-12">
        <aside className="curamind-profile-welcome flex flex-col justify-center rounded-3xl border border-line bg-white p-6 sm:p-8 lg:min-h-[560px]">
          <Image
            src="/curamind-logo.jpeg"
            alt={t("home.logoAlt")}
            width={520}
            height={180}
            priority
            className="mb-8 h-auto w-[180px] max-w-full object-contain sm:w-[220px]"
          />

          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-line bg-brand-soft px-3 py-1.5 text-sm font-medium text-brand">
            <Icon name="heart" className="h-4 w-4" />
            {t("home.brand")}
          </span>

          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            {t("home.welcomeTitle")}
          </h1>

          <p className="mt-4 text-base leading-7 text-muted">
            {t("home.welcomeText")}
          </p>

          <div className="mt-8 grid grid-cols-3 gap-3 text-center">
            <div className="rounded-2xl bg-brand-soft p-3">
              <Icon name="shield" className="mx-auto h-5 w-5 text-brand" />
              <p className="mt-2 text-xs font-semibold text-ink">{t("home.private")}</p>
            </div>

            <div className="rounded-2xl bg-brand-soft p-3">
              <Icon name="heart" className="mx-auto h-5 w-5 text-brand" />
              <p className="mt-2 text-xs font-semibold text-ink">{t("home.personal")}</p>
            </div>

            <div className="rounded-2xl bg-brand-soft p-3">
              <Icon name="activity" className="mx-auto h-5 w-5 text-brand" />
              <p className="mt-2 text-xs font-semibold text-ink">{t("home.connected")}</p>
            </div>
          </div>
        </aside>

        <div className="min-w-0 space-y-6">
          <header className="flex flex-wrap items-center justify-between gap-3">
            <nav aria-label="Account access" className="flex flex-wrap items-center gap-2">
              <Link href="/" className="rounded-xl border border-line bg-white px-3 py-2 text-sm font-medium text-[#123C46] hover:bg-brand-soft">
                Continue as Guest
              </Link>
              <Link href="/login" className="rounded-xl px-3 py-2 text-sm font-medium text-[#123C46] hover:bg-brand-soft">
                Log In
              </Link>
              <Link href="/register" className="rounded-xl bg-brand px-3 py-2 text-sm font-semibold text-white hover:opacity-90">
                Create Account
              </Link>
            </nav>
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
                {t("home.brand")}
              </div>

              <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
                {t("home.chooseProfile")}
              </h1>

              <p className="max-w-xl text-base leading-7 text-muted">
                {t("home.chooseProfileText")}
              </p>
            </div>
          </section>

          <section className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold">{t("home.profiles")}</h2>
              <p className="mt-1 text-sm text-muted">
                {t("home.profilesSub")}
              </p>
            </div>

            {loading ? (
              <div className="card p-6 text-sm text-muted">
                {t("home.loading")}
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
                      {profile.name || t("home.myProfile")}
                    </span>

                    <span className="mt-1 block text-sm text-muted">
                      {t("home.myRecords")}
                    </span>

                    <span className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-brand">
                      {t("home.continueRecords")}
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
                      {t("home.profileSettings")}
                    </span>

                    <span className="mt-1 block text-sm leading-6 text-muted">
                      {t("home.profileSettingsText")}
                    </span>

                    <span className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-brand">
                      {t("home.manageProfile")}
                      <Icon name="chevron" className="h-4 w-4" />
                    </span>
                  </span>
                </Link>
              </div>
            ) : (
              <div className="card p-5 text-sm text-muted">
                {t("home.profileUnavailable")}
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
            <h2 className="text-xl font-semibold">Profiles</h2>
            <p className="mt-1 text-sm leading-6 text-muted">
              {t("home.familyText")}
            </p>
          </div>
        </div>

        {familyMembers.length === 0 ? (
          <div className="rounded-xl border border-dashed border-line p-4">
            <p className="font-medium">{t("home.noFamily")}</p>
            <p className="mt-1 text-sm leading-6 text-muted">
              {t("home.noFamilyText")}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {familyMembers.map((member) => (
              <div
                key={member.oid}
                className="flex items-center justify-between gap-4 rounded-xl border border-line bg-white p-4"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-brand-soft font-semibold text-brand">
                    {member.name.trim().charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate font-medium">{member.name}</p>
                    <p className="text-sm text-muted">
                      {member.dob || "Date of birth not added"}
                      {member.sex ? ` · ${member.sex}` : ""}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn"
                  onClick={async () => {
                    if (!window.confirm(`Remove ${member.name} from your family list?`)) return;
                    try {
                      await familyApi.remove(member.oid);
                      await loadFamilyMembers();
                      setNotice("Family member removed from your list.");
                    } catch (error) {
                      setNotice(error instanceof Error ? error.message : "Could not remove family member.");
                    }
                  }}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setShowAdd((value) => !value);
            setNotice("");
          }}
        >
          <Icon name="plus" className="h-4 w-4" />
          {showAdd ? t("home.closeForm") : "+ Add profile"}
        </button>

        {showAdd && (
          <form
            onSubmit={handleAddMember}
            className="space-y-5 border-t border-line pt-5"
          >
            <h3 className="font-semibold">{t("home.familyDetails")}</h3>

            <p className="text-sm leading-6 text-muted">
              {t("home.previewOnly")}
            </p>

            <div>
              <h4 className="text-sm font-semibold">{t("home.basicInfo")}</h4>

              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <label className="block space-y-1.5 text-sm font-medium">
                  {t("home.fullName")} *
                  <input
                    required
                    value={memberName}
                    onChange={(event) => setMemberName(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                    placeholder={t("home.fullNamePlaceholder")}
                  />
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  {t("home.dob")}
                  <input
                    type="date"
                    value={dateOfBirth}
                    onChange={(event) => setDateOfBirth(event.target.value)}
                    max={new Date().toISOString().slice(0, 10)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                  />
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  {t("home.age")}
                  <input
                    type="number"
                    min="0"
                    max="125"
                    value={age}
                    onChange={(event) => setAge(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                    placeholder={t("home.agePlaceholder")}
                  />
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  Gender
                  <select
                    value={gender}
                    onChange={(event) => setGender(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                  >
                    <option value="">{t("home.selectGender")}</option>
                    <option value="female">{t("home.female")}</option>
                    <option value="male">{t("home.male")}</option>
                    <option value="other">{t("home.other")}</option>
                    <option value="prefer_not_to_say">
                      {t("home.preferNot")}
                    </option>
                  </select>
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  {t("home.bloodType")}
                  <select
                    value={bloodGroup}
                    onChange={(event) => setBloodGroup(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-surface px-3 text-ink"
                  >
                    <option value="">{t("home.unknownBlood")}</option>
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
            <div className="rounded-2xl border border-line bg-brand-soft p-4">
              <h4 className="font-semibold">{t("home.emergencyContact")}</h4>
              <p className="mt-1 text-sm text-muted">
                {t("home.optionalFields")}
              </p>

              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <label className="block space-y-1.5 text-sm font-medium">
                  {t("home.contactName")}
                  <input
                    value={emergencyName}
                    onChange={(event) => setEmergencyName(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-white px-3 text-ink"
                    placeholder={t("home.contactNamePlaceholder")}
                  />
                </label>

                <label className="block space-y-1.5 text-sm font-medium">
                  {t("home.contactPhone")}
                  <input
                    type="tel"
                    value={emergencyPhone}
                    onChange={(event) => setEmergencyPhone(event.target.value)}
                    className="min-h-11 w-full rounded-xl border border-line bg-white px-3 text-ink"
                    placeholder={t("home.contactPhonePlaceholder")}
                  />
                </label>
              </div>
            </div>

            <p className="text-xs leading-5 text-muted">
              {t("home.requiredNote")}
            </p>

            <button type="submit" className="btn btn-primary">
              {t("home.reviewSetup")}
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
        {t("home.footer")}
      </p>
    </div>
  );
}
