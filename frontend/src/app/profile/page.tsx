"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { api, Profile, WomensHealthProfile } from "@/api";
import Icon from "@/components/Icon";
import { useProfile } from "@/Shell";
import { LANGS, Lang } from "@/i18n";
import { useToast } from "@/components/Toast";

const EMPTY_WOMENS_HEALTH_PROFILE: WomensHealthProfile = {
  cycle_tracker_enabled: false,
  pregnancy_tracker_enabled: false,
  menopause_fertility_enabled: false,
  screening_enabled: false,
  last_period_date: null,
  period_start_dates: [],
  cycle_length_days: null,
  pregnancy_status: "unknown",
  estimated_due_date: null,
  pregnancy_notes: null,
  menopause_notes: null,
  fertility_notes: null,
  cervical_screening_notes: null,
  breast_health_notes: null,
};

export default function ProfilePage() {
  const { t, i18n } = useTranslation();
  const { profile, reload } = useProfile();
  const toast = useToast();
  const router = useRouter();

  const [setupMode, setSetupMode] = useState(false);
  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [sex, setSex] = useState("");
  const [language, setLanguage] = useState<Lang>("en");
  const [voiceLanguage, setVoiceLanguage] = useState<Lang>("en");
  const [voiceReminders, setVoiceReminders] = useState(false);
  const [familyReminders, setFamilyReminders] = useState(false);
  const [womensHealth, setWomensHealth] = useState<WomensHealthProfile>(EMPTY_WOMENS_HEALTH_PROFILE);
  const [periodEntryDate, setPeriodEntryDate] = useState("");
  const [womensHealthSaving, setWomensHealthSaving] = useState(false);
  const [womensHealthMessage, setWomensHealthMessage] = useState("");
  const [womensHealthError, setWomensHealthError] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setSetupMode(new URLSearchParams(window.location.search).get("setup") === "1");
  }, []);

  useEffect(() => {
    if (!profile) return;
    setName(profile.name || "");
    setDob(profile.dob || "");
    setSex(profile.sex || "");
    setLanguage((profile.language in LANGS ? profile.language : "en") as Lang);
    setVoiceLanguage((profile.voice_language in LANGS ? profile.voice_language : "en") as Lang);
    setVoiceReminders(profile.voice_reminders_enabled);
    setFamilyReminders(profile.family_reminders_enabled);
    setWomensHealth({
      ...EMPTY_WOMENS_HEALTH_PROFILE,
      ...profile.womens_health_profile,
    });
    setPeriodEntryDate(new Date().toISOString().slice(0, 10));
  }, [profile]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");

    if (!name.trim()) {
      setError(t("profile.nameRequired"));
      return;
    }

    setSaving(true);

    try {
      const payload: {
        name: string;
        sex?: string;
        dob?: string;
        preferred_language: string;
        preferred_voice_language: Lang;
        voice_reminders_enabled: boolean;
        family_reminders_enabled: boolean;
      } = {
        name: name.trim(),
        preferred_language: language,
        preferred_voice_language: voiceLanguage,
        voice_reminders_enabled: voiceReminders,
        family_reminders_enabled: familyReminders,
      };

      if (sex) payload.sex = sex;
      if (dob) payload.dob = dob;

      await api.updateProfile(payload);
      await i18n.changeLanguage(language);
      try {
        localStorage.setItem("lang", language);
      } catch {
        // Language still changes for the current session.
      }
      reload();
      if (setupMode) {
        router.replace("/health");
        return;
      }
      setMessage(t("profile.saved"));
    } catch {
      setError(t("profile.error"));
    } finally {
      setSaving(false);
    }
  }

  function setWomenFeature(
    feature: "cycle_tracker_enabled" | "pregnancy_tracker_enabled" | "menopause_fertility_enabled" | "screening_enabled",
    enabled: boolean,
  ) {
    setWomensHealth((current) => {
      const next = { ...current, [feature]: enabled };
      if (!enabled && feature === "cycle_tracker_enabled") {
        next.last_period_date = null;
        next.period_start_dates = [];
        next.cycle_length_days = null;
      } else if (!enabled && feature === "pregnancy_tracker_enabled") {
        next.pregnancy_status = "unknown";
        next.estimated_due_date = null;
        next.pregnancy_notes = null;
      } else if (!enabled && feature === "menopause_fertility_enabled") {
        next.menopause_notes = null;
        next.fertility_notes = null;
      } else if (!enabled && feature === "screening_enabled") {
        next.cervical_screening_notes = null;
        next.breast_health_notes = null;
      }
      return next;
    });
    setWomensHealthMessage("");
    setWomensHealthError("");
  }

  async function handleWomensHealthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWomensHealthMessage("");
    setWomensHealthError("");
    setWomensHealthSaving(true);
    try {
      await api.updateProfile({ womens_health_profile: womensHealth });
      await reload();
      setWomensHealthMessage(t("profile.womensHealthSaved"));
    } catch {
      setWomensHealthError(t("profile.error"));
    } finally {
      setWomensHealthSaving(false);
    }
  }

  function addPeriodStartDate() {
    if (
      !periodEntryDate
      || womensHealth.period_start_dates.includes(periodEntryDate)
      || womensHealth.period_start_dates.length >= 60
    ) return;
    const periodDates = [...womensHealth.period_start_dates, periodEntryDate].sort();
    setWomensHealth((current) => ({
      ...current,
      period_start_dates: periodDates,
      last_period_date: periodDates[periodDates.length - 1],
    }));
    setWomensHealthMessage("");
    setWomensHealthError("");
  }

  function removePeriodStartDate(periodDate: string) {
    const periodDates = womensHealth.period_start_dates.filter((day) => day !== periodDate);
    setWomensHealth((current) => ({
      ...current,
      period_start_dates: periodDates,
      last_period_date: periodDates[periodDates.length - 1] ?? null,
    }));
    setWomensHealthMessage("");
    setWomensHealthError("");
  }

  const countCards = [
    { label: t("profile.conditions"), count: profile?.conditions?.length ?? 0 },
    { label: t("profile.medications"), count: profile?.current_medicines?.length ?? 0 },
    { label: t("profile.allergies"), count: profile?.allergies?.length ?? 0 },
  ];
  const recentPeriodDates = womensHealth.period_start_dates.slice(-7);
  const cycleIntervals = recentPeriodDates.slice(1).map((periodDate, index) => {
    const current = Date.parse(`${periodDate}T00:00:00Z`);
    const previous = Date.parse(`${recentPeriodDates[index]}T00:00:00Z`);
    return Math.round((current - previous) / 86_400_000);
  });
  const averageRecordedCycle = cycleIntervals.length
    ? Math.round(cycleIntervals.reduce((total, interval) => total + interval, 0) / cycleIntervals.length)
    : null;

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Image src="/curamind-logo.jpeg" alt={t("profile.logoAlt")} width={520} height={180} className="h-auto w-[145px] max-w-full object-contain sm:w-[175px]" />
          <div>
            <p className="text-xl font-bold text-[#123C46]">CuraMind</p>
            <p className="text-xs text-muted">{t("profile.brandTagline")}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-sm font-medium text-[#123C46]">
            <span>{t("language")}</span>
            <select
              aria-label={t("language")}
              className="min-h-10 rounded-xl border border-[#B9DED5] bg-white px-3 text-[#123C46]"
              value={i18n.language in LANGS ? i18n.language : "en"}
              onChange={(event) => {
                const next = event.target.value as Lang;
                setLanguage(next);
                void i18n.changeLanguage(next);
                try { localStorage.setItem("lang", next); } catch {}
                api.setLanguage(next).catch(() => toast(t("profile.languageSaveError"), true));
              }}
            >
              {(Object.keys(LANGS) as Lang[]).map((key) => (
                <option key={key} value={key}>{LANGS[key]}</option>
              ))}
            </select>
          </label>
          {setupMode ? (
            <Link href="/health" className="btn btn-ghost border border-[#B9DED5] bg-white text-[#123C46]">{t("profile.skipSetup")}</Link>
          ) : (
            <Link href="/" className="btn btn-ghost border border-[#B9DED5] bg-white text-[#123C46]">{t("profile.switchProfile")}</Link>
          )}
        </div>
        <div className="w-full">
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{setupMode ? t("profile.setupTitle") : t("profile.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">{setupMode ? t("profile.setupSubtitle") : t("profile.subtitle")}</p>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {countCards.map((card) => (
          <div key={card.label} className="card p-5">
            <p className="text-sm text-muted">{card.label}</p>
            <p className="mt-2 text-2xl font-semibold tabular-nums">{card.count}</p>
          </div>
        ))}
      </section>

      <section className="card overflow-hidden p-5 sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-4">
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-[#DDF5EE] text-[#123C46]">
              <span aria-hidden="true" className="text-xl">?</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[#123C46]">{t("profile.documentsTitle")}</h2>
              <p className="mt-1 max-w-xl text-sm text-muted">
                {t("profile.documentsDescription")}
              </p>
            </div>
          </div>
          <Link href="/upload" className="btn btn-primary inline-flex shrink-0 items-center justify-center gap-2">
            <span aria-hidden="true">?</span> {t("profile.uploadDocument")}
          </Link>
        </div>
        <div className="mt-5 grid grid-cols-1 gap-3 border-t border-line pt-4 sm:grid-cols-3">
          <div className="rounded-xl bg-surface-2 p-3">
            <p className="text-sm font-semibold">{t("profile.prescriptions")}</p>
            <p className="mt-1 text-xs text-muted">{t("profile.prescriptionsDescription")}</p>
          </div>
          <div className="rounded-xl bg-surface-2 p-3">
            <p className="text-sm font-semibold">{t("profile.labReports")}</p>
            <p className="mt-1 text-xs text-muted">{t("profile.labReportsDescription")}</p>
          </div>
          <div className="rounded-xl bg-surface-2 p-3">
            <p className="text-sm font-semibold">{t("profile.healthRecords")}</p>
            <p className="mt-1 text-xs text-muted">{t("profile.healthRecordsDescription")}</p>
          </div>
        </div>
      </section>

      <section className="card p-5 sm:p-7">
        <div className="relative overflow-hidden rounded-2xl border border-rose-200/70 bg-gradient-to-br from-rose-50 via-white to-brand-soft p-5 sm:p-6">
          <div className="relative z-10 max-w-3xl">
            <p className="eyebrow flex items-center gap-2 text-rose-700">
              <Icon name="heart" className="h-4 w-4" />
              {t("profile.womensHealthTitle")}
            </p>
            <h2 className="mt-2 text-xl font-semibold text-ink sm:text-2xl">{t("profile.womensHealthHeading")}</h2>
            <p className="mt-2 text-sm leading-6 text-muted">{t("profile.womensHealthDescription")}</p>
            <p className="mt-2 text-xs leading-5 text-muted">{t("profile.womensHealthPrivacy")}</p>
          </div>
          <Icon name="sparkles" className="absolute -right-2 -top-3 h-24 w-24 text-rose-200/70" />
        </div>
        <form onSubmit={handleWomensHealthSubmit} className="mt-5 space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            {([
              ["cycle_tracker_enabled", "cycleTracker", "cycleTrackerDescription", "calendar"],
              ["pregnancy_tracker_enabled", "pregnancyTracker", "pregnancyTrackerDescription", "heart"],
              ["menopause_fertility_enabled", "menopauseFertility", "menopauseFertilityDescription", "sparkles"],
              ["screening_enabled", "screening", "screeningDescription", "shield"],
            ] as const).map(([feature, title, description, icon]) => (
              <label
                key={feature}
                className={`group flex cursor-pointer items-start gap-3 rounded-2xl border p-4 text-sm transition hover:-translate-y-0.5 hover:shadow-card ${
                  womensHealth[feature]
                    ? "border-rose-300 bg-rose-50/70 ring-1 ring-rose-200"
                    : "border-line bg-surface hover:border-rose-200"
                }`}
              >
                <input
                  type="checkbox"
                  checked={womensHealth[feature]}
                  onChange={(event) => setWomenFeature(feature, event.target.checked)}
                  className="mt-1 h-4 w-4 accent-rose-600"
                />
                <span>
                  <span className="flex items-center gap-2 font-semibold text-ink">
                    <Icon name={icon} className="h-4 w-4 text-rose-700" />
                    {t(`profile.${title}`)}
                  </span>
                  <span className="mt-1.5 block text-xs font-normal leading-5 text-muted">{t(`profile.${description}`)}</span>
                </span>
              </label>
            ))}
          </div>

          {womensHealth.cycle_tracker_enabled && (
            <fieldset className="space-y-4 rounded-2xl border border-rose-200 bg-rose-50/30 p-4 sm:p-5">
              <legend className="px-2 text-sm font-semibold text-rose-900">{t("profile.cycleTracker")}</legend>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="text-sm">
                  {t("profile.periodStartDate")}
                  <input
                    className="input mt-1 w-full"
                    type="date"
                    max={new Date().toISOString().slice(0, 10)}
                    value={periodEntryDate}
                    onChange={(event) => setPeriodEntryDate(event.target.value)}
                  />
                  <button type="button" className="btn btn-ghost mt-2" onClick={addPeriodStartDate} disabled={!periodEntryDate || womensHealth.period_start_dates.includes(periodEntryDate) || womensHealth.period_start_dates.length >= 60}>
                    {t("profile.addPeriodStartDate")}
                  </button>
                </label>
                <label className="text-sm">
                  {t("profile.cycleLength")}
                  <input
                    className="input mt-1 w-full"
                    type="number"
                    min={1}
                    max={366}
                    value={womensHealth.cycle_length_days ?? ""}
                    onChange={(event) => setWomensHealth((current) => ({ ...current, cycle_length_days: event.target.value ? Number(event.target.value) : null }))}
                  />
                </label>
              </div>
              {womensHealth.period_start_dates.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium">{t("profile.periodHistory")}</h3>
                  {averageRecordedCycle !== null && (
                    <p className="mt-1 text-sm text-muted">
                      {t("profile.averageRecordedCycle", { days: averageRecordedCycle })}
                    </p>
                  )}
                  <ul className="mt-2 space-y-2">
                    {[...womensHealth.period_start_dates].reverse().map((periodDate) => (
                      <li key={periodDate} className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-2 text-sm">
                        <time dateTime={periodDate}>{new Date(`${periodDate}T00:00:00`).toLocaleDateString(i18n.language)}</time>
                        <button type="button" className="text-crit underline" onClick={() => removePeriodStartDate(periodDate)}>
                          {t("profile.removePeriodEntry")}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="text-xs text-muted">{t("profile.cycleTrackerDisclaimer")}</p>
            </fieldset>
          )}

          {womensHealth.pregnancy_tracker_enabled && (
            <fieldset className="space-y-3 rounded-2xl border border-rose-200 bg-rose-50/30 p-4 sm:p-5">
              <legend className="px-2 text-sm font-semibold text-rose-900">{t("profile.pregnancyTracker")}</legend>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="text-sm">
                  {t("profile.pregnancyStatus")}
                  <select
                    className="input mt-1 w-full"
                    value={womensHealth.pregnancy_status}
                    onChange={(event) => setWomensHealth((current) => ({ ...current, pregnancy_status: event.target.value as WomensHealthProfile["pregnancy_status"] }))}
                  >
                    <option value="unknown">{t("profile.statusUnknown")}</option>
                    <option value="pregnant">{t("profile.statusPregnant")}</option>
                    <option value="not_pregnant">{t("profile.statusNotPregnant")}</option>
                    <option value="postpartum">{t("profile.statusPostpartum")}</option>
                  </select>
                </label>
                <label className="text-sm">
                  {t("profile.estimatedDueDate")}
                  <input
                    className="input mt-1 w-full"
                    type="date"
                    value={womensHealth.estimated_due_date ?? ""}
                    onChange={(event) => setWomensHealth((current) => ({ ...current, estimated_due_date: event.target.value || null }))}
                  />
                </label>
              </div>
              <label className="block text-sm">
                {t("profile.pregnancyNotes")}
                <textarea className="input mt-1 w-full" rows={3} maxLength={2000} value={womensHealth.pregnancy_notes ?? ""} onChange={(event) => setWomensHealth((current) => ({ ...current, pregnancy_notes: event.target.value || null }))} />
              </label>
            </fieldset>
          )}

          {womensHealth.menopause_fertility_enabled && (
            <fieldset className="space-y-3 rounded-2xl border border-rose-200 bg-rose-50/30 p-4 sm:p-5">
              <legend className="px-2 text-sm font-semibold text-rose-900">{t("profile.menopauseFertility")}</legend>
              <label className="block text-sm">
                {t("profile.menopauseNotes")}
                <textarea className="input mt-1 w-full" rows={3} maxLength={2000} value={womensHealth.menopause_notes ?? ""} onChange={(event) => setWomensHealth((current) => ({ ...current, menopause_notes: event.target.value || null }))} />
              </label>
              <label className="block text-sm">
                {t("profile.fertilityNotes")}
                <textarea className="input mt-1 w-full" rows={3} maxLength={2000} value={womensHealth.fertility_notes ?? ""} onChange={(event) => setWomensHealth((current) => ({ ...current, fertility_notes: event.target.value || null }))} />
              </label>
            </fieldset>
          )}

          {womensHealth.screening_enabled && (
            <fieldset className="space-y-3 rounded-2xl border border-rose-200 bg-rose-50/30 p-4 sm:p-5">
              <legend className="px-2 text-sm font-semibold text-rose-900">{t("profile.screening")}</legend>
              <label className="block text-sm">
                {t("profile.cervicalScreening")}
                <textarea className="input mt-1 w-full" rows={3} maxLength={2000} value={womensHealth.cervical_screening_notes ?? ""} onChange={(event) => setWomensHealth((current) => ({ ...current, cervical_screening_notes: event.target.value || null }))} />
              </label>
              <label className="block text-sm">
                {t("profile.breastHealth")}
                <textarea className="input mt-1 w-full" rows={3} maxLength={2000} value={womensHealth.breast_health_notes ?? ""} onChange={(event) => setWomensHealth((current) => ({ ...current, breast_health_notes: event.target.value || null }))} />
              </label>
            </fieldset>
          )}

          {womensHealthMessage && <p role="status" className="text-sm text-ok">{womensHealthMessage}</p>}
          {womensHealthError && <p role="alert" className="text-sm text-crit">{womensHealthError}</p>}

          <div className="flex justify-end border-t border-line pt-5">
            <button type="submit" className="btn btn-primary" disabled={womensHealthSaving}>
              {womensHealthSaving ? t("profile.saving") : t("profile.saveWomensHealth")}
            </button>
          </div>
        </form>
      </section>

      <section className="card p-5 sm:p-7">
        <h2 className="text-lg font-semibold">{t("profile.personal")}</h2>
        <form onSubmit={handleSubmit} className="mt-5 space-y-5">
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <label className="block text-sm font-medium">
              {t("profile.name")}
              <input
                className="input mt-2 w-full"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={120}
                autoComplete="name"
                placeholder={t("profile.name")}
              />
            </label>

            <label className="block text-sm font-medium">
              {t("profile.dob")}
              <input
                className="input mt-2 w-full"
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                max={new Date().toISOString().slice(0, 10)}
              />
            </label>

            <label className="block text-sm font-medium">
              {t("profile.sex")}
              <select className="input mt-2 w-full" value={sex} onChange={(e) => setSex(e.target.value)}>
                <option value="">{t("profile.selectSex")}</option>
                <option value="female">{t("profile.female")}</option>
                <option value="male">{t("profile.male")}</option>
                <option value="other">{t("profile.other")}</option>
                <option value="prefer_not_to_say">{t("profile.preferNotToSay")}</option>
              </select>
            </label>

            <label className="block text-sm font-medium">
              {t("profile.language")}
              <select
                className="input mt-2 w-full"
                value={language}
                onChange={(e) => setLanguage(e.target.value as Lang)}
              >
                {(Object.keys(LANGS) as Lang[]).map((key) => (
                  <option key={key} value={key}>{LANGS[key]}</option>
                ))}
              </select>
            </label>

            <label className="block text-sm font-medium">
              {t("profile.voiceLanguage")}
              <select
                className="input mt-2 w-full"
                value={voiceLanguage}
                onChange={(e) => setVoiceLanguage(e.target.value as Lang)}
              >
                {(Object.keys(LANGS) as Lang[]).map((key) => (
                  <option key={key} value={key}>{LANGS[key]}</option>
                ))}
              </select>
              <span className="mt-1 block text-xs font-normal text-muted">{t("profile.voiceLanguageDescription")}</span>
            </label>
            <label className="flex items-start gap-3 rounded-xl border border-line p-3 text-sm">
              <input
                type="checkbox"
                checked={voiceReminders}
                onChange={(e) => setVoiceReminders(e.target.checked)}
                className="mt-1"
              />
              <span>
                <span className="block font-medium">{t("profile.voiceReminders")}</span>
                <span className="mt-1 block text-xs font-normal text-muted">{t("profile.voiceRemindersDescription")}</span>
              </span>
            </label>
            <label className="flex items-start gap-3 rounded-xl border border-line p-3 text-sm">
              <input
                type="checkbox"
                checked={familyReminders}
                onChange={(event) => setFamilyReminders(event.target.checked)}
                className="mt-1"
              />
              <span>
                <span className="block font-medium">{t("profile.familyReminders")}</span>
                <span className="mt-1 block text-xs font-normal text-muted">{t("profile.familyRemindersDescription")}</span>
              </span>
            </label>
          </div>

          {message && <p role="status" className="text-sm text-ok">{message}</p>}
          {error && <p role="alert" className="text-sm text-crit">{error}</p>}

          <div className="flex justify-end border-t border-line pt-5">
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? t("profile.saving") : setupMode ? t("profile.saveAndContinue") : t("profile.save")}
            </button>
          </div>
        </form>
      </section>

      <section className="card p-5 sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">{t("profile.abhaTitle")}</h2>
            <p className="mt-1 text-sm text-muted">{t("profile.abhaDescription")}</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
            profile?.abha.linked
              ? "bg-ok-soft text-ok"
              : "bg-surface-2 text-muted ring-1 ring-line"
          }`}>
            {profile?.abha.linked ? t("profile.linked") : t("profile.notVerified")}
          </span>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-line p-4">
            <p className="text-sm text-muted">{t("profile.abhaNumber")}</p>
            <p className="mt-2 break-all font-medium">{profile?.abha.number || t("profile.notAdded")}</p>
          </div>
          <div className="rounded-xl border border-line p-4">
            <p className="text-sm text-muted">{t("profile.abhaAddress")}</p>
            <p className="mt-2 break-all font-medium">{profile?.abha.address || t("profile.notAdded")}</p>
          </div>
        </div>

        <p className="mt-4 text-xs text-muted">
          {t("profile.demoDisclaimer")}
        </p>

        <div className="mt-4">
          <a href="/abha" className="btn btn-primary inline-flex">{t("profile.manageAbha")}</a>
        </div>
      </section>
      <section className="card p-5 sm:p-7">
        <h2 className="text-lg font-semibold">{t("profile.overview")}</h2>
        <p className="mt-2 text-sm text-muted">{t("profile.privacy")}</p>

        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold">{t("profile.conditions")}</h3>
            {profile?.conditions?.length ? (
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm">
                {profile.conditions.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
              </ul>
            ) : <p className="mt-2 text-sm text-muted">{t("none")}</p>}
          </div>

          <div>
            <h3 className="text-sm font-semibold">{t("profile.allergies")}</h3>
            {profile?.allergies?.length ? (
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm">
                {profile.allergies.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}
              </ul>
            ) : <p className="mt-2 text-sm text-muted">{t("none")}</p>}
          </div>
        </div>
      </section>
    </main>
  );
}
