"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { api, WomensHealthProfile } from "@/api";
import Icon from "@/components/Icon";
import { useProfile } from "@/Shell";

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

function localDateInputValue(value = new Date()) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export default function WomensHealthPage() {
  const { t, i18n } = useTranslation();
  const { profile, reload } = useProfile();
  const [womensHealth, setWomensHealth] = useState<WomensHealthProfile>(EMPTY_WOMENS_HEALTH_PROFILE);
  const [periodEntryDate, setPeriodEntryDate] = useState(localDateInputValue());
  const [saving, setSaving] = useState(false);
  const [reminderSaving, setReminderSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!profile) return;
    setWomensHealth({
      ...EMPTY_WOMENS_HEALTH_PROFILE,
      ...profile.womens_health_profile,
    });
    setPeriodEntryDate(localDateInputValue());
  }, [profile]);

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
    setMessage("");
    setError("");
  }

  async function saveWomensHealth(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setMessage("");
    setError("");
    setSaving(true);
    try {
      await api.updateProfile({ womens_health_profile: womensHealth });
      reload();
      setMessage(t("profile.womensHealthSaved"));
    } catch {
      setError(t("profile.error"));
    } finally {
      setSaving(false);
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
    setMessage("");
    setError("");
  }

  function removePeriodStartDate(periodDate: string) {
    const periodDates = womensHealth.period_start_dates.filter((day) => day !== periodDate);
    setWomensHealth((current) => ({
      ...current,
      period_start_dates: periodDates,
      last_period_date: periodDates[periodDates.length - 1] ?? null,
    }));
    setMessage("");
    setError("");
  }

  const recentPeriodDates = womensHealth.period_start_dates.slice(-7);
  const cycleIntervals = recentPeriodDates.slice(1).map((periodDate, index) => {
    const current = Date.parse(`${periodDate}T00:00:00Z`);
    const previous = Date.parse(`${recentPeriodDates[index]}T00:00:00Z`);
    return Math.round((current - previous) / 86_400_000);
  });
  const averageRecordedCycle = cycleIntervals.length >= 2
    ? Math.round(cycleIntervals.reduce((total, interval) => total + interval, 0) / cycleIntervals.length)
    : null;
  const estimateCycleLength = womensHealth.cycle_length_days ?? averageRecordedCycle;
  const latestPeriodDate = womensHealth.period_start_dates.at(-1) ?? null;
  const estimatePeriodDate = latestPeriodDate && estimateCycleLength
    ? new Date(Date.parse(`${latestPeriodDate}T00:00:00Z`) + estimateCycleLength * 86_400_000)
        .toISOString()
        .slice(0, 10)
    : null;
  const estimateRange = averageRecordedCycle !== null && cycleIntervals.length >= 2 && latestPeriodDate
    ? {
        earliest: new Date(Date.parse(`${latestPeriodDate}T00:00:00Z`) + Math.min(...cycleIntervals) * 86_400_000).toISOString().slice(0, 10),
        latest: new Date(Date.parse(`${latestPeriodDate}T00:00:00Z`) + Math.max(...cycleIntervals) * 86_400_000).toISOString().slice(0, 10),
      }
    : null;
  const localToday = new Date();
  const todayDateOnly = new Date(Date.UTC(
    localToday.getFullYear(),
    localToday.getMonth(),
    localToday.getDate(),
  ));
  const nextPeriodEstimate = estimatePeriodDate
    ? {
        date: estimatePeriodDate,
        daysPast: Math.max(
          0,
          Math.floor(
            (todayDateOnly.getTime() - Date.parse(`${estimatePeriodDate}T00:00:00Z`))
            / 86_400_000,
          ),
        ),
      }
    : null;
  const formatPeriodDate = (value: string) => new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));

  async function createPeriodCheckInReminder() {
    if (!nextPeriodEstimate) return;
    setError("");
    setMessage("");
    setReminderSaving(true);
    try {
      await api.updateProfile({ womens_health_profile: womensHealth });
    } catch {
      setError(t("profile.error"));
      setReminderSaving(false);
      return;
    }
    try {
      const dueAt = new Date(`${nextPeriodEstimate.date}T09:00:00`);
      dueAt.setDate(dueAt.getDate() + 7);
      if (dueAt.getTime() <= Date.now()) {
        dueAt.setTime(Date.now());
        dueAt.setDate(dueAt.getDate() + 1);
        dueAt.setHours(9, 0, 0, 0);
      }
      await api.createReminder({
        title: t("profile.periodReminderTitle"),
        details: t("profile.periodReminderDetails"),
        due_at: dueAt.toISOString(),
        category: "wellness",
        recurrence: "none",
      });
      setMessage(t("profile.periodReminderSaved"));
    } catch {
      setError(t("profile.periodReminderError"));
    } finally {
      setReminderSaving(false);
    }
  }

  const featureOptions = [
    ["cycle_tracker_enabled", "cycleTracker", "cycleTrackerDescription", "calendar"],
    ["pregnancy_tracker_enabled", "pregnancyTracker", "pregnancyTrackerDescription", "heart"],
    ["menopause_fertility_enabled", "menopauseFertility", "menopauseFertilityDescription", "sparkles"],
    ["screening_enabled", "screening", "screeningDescription", "shield"],
  ] as const;

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6">
      <header className="relative overflow-hidden rounded-3xl border border-rose-200/70 bg-gradient-to-br from-rose-50 via-white to-brand-soft p-6 shadow-card sm:p-8">
        <Icon name="sparkles" className="absolute -right-2 -top-3 h-24 w-24 text-rose-200/70" />
        <p className="eyebrow flex items-center gap-2 text-rose-700">
          <Icon name="heart" className="h-4 w-4" />
          {t("profile.womensHealthTitle")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-ink sm:text-3xl">{t("profile.womensHealthHeading")}</h1>
        <p className="relative mt-2 max-w-3xl text-sm leading-6 text-muted">{t("profile.womensHealthDescription")}</p>
        <p className="relative mt-2 text-xs leading-5 text-muted">{t("profile.womensHealthPrivacy")}</p>
      </header>

      <form onSubmit={(event) => void saveWomensHealth(event)} className="card space-y-5 p-5 sm:p-7">
        <div className="grid gap-3 sm:grid-cols-2">
          {featureOptions.map(([feature, title, description, icon]) => (
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
                  max={localDateInputValue()}
                  value={periodEntryDate}
                  onChange={(event) => setPeriodEntryDate(event.target.value)}
                />
                <button type="button" className="btn btn-ghost mt-2" onClick={addPeriodStartDate} disabled={!periodEntryDate || womensHealth.period_start_dates.includes(periodEntryDate) || womensHealth.period_start_dates.length >= 60}>
                  {t("profile.addPeriodStartDate")}
                </button>
                <button
                  type="button"
                  className="btn btn-soft mt-2 sm:ml-2"
                  onClick={() => {
                    const today = localDateInputValue();
                    setPeriodEntryDate(today);
                    if (!womensHealth.period_start_dates.includes(today) && womensHealth.period_start_dates.length < 60) {
                      const periodDates = [...womensHealth.period_start_dates, today].sort();
                      setWomensHealth((current) => ({
                        ...current,
                        period_start_dates: periodDates,
                        last_period_date: periodDates[periodDates.length - 1],
                      }));
                      setMessage("");
                      setError("");
                    }
                  }}
                  disabled={womensHealth.period_start_dates.includes(localDateInputValue()) || womensHealth.period_start_dates.length >= 60}
                >
                  {t("profile.recordPeriodToday")}
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
            {nextPeriodEstimate ? (
              <div className="rounded-xl border border-rose-200 bg-white/80 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-rose-800">{t("profile.nextPeriodEstimate")}</p>
                <p className="mt-1 text-lg font-semibold text-ink">
                  {estimateRange
                    ? t("profile.estimatedPeriodWindow", {
                        start: formatPeriodDate(estimateRange.earliest),
                        end: formatPeriodDate(estimateRange.latest),
                      })
                    : formatPeriodDate(nextPeriodEstimate.date)}
                </p>
                <p className="mt-1 text-xs leading-5 text-muted">{t("profile.periodEstimateBasis", { days: estimateCycleLength })}</p>
                {nextPeriodEstimate.daysPast >= 7 && (
                  <>
                    <p role="status" className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm leading-5 text-amber-950">
                      {t("profile.periodEstimatePassed", { days: nextPeriodEstimate.daysPast })}
                    </p>
                    <p className="mt-2 text-xs leading-5 text-muted">{t("profile.periodLateGuidance")}</p>
                  </>
                )}
                <button
                  type="button"
                  className="btn btn-soft mt-3"
                  onClick={() => void createPeriodCheckInReminder()}
                  disabled={reminderSaving}
                >
                  <Icon name="bell" className="h-4 w-4" />
                  {reminderSaving ? t("profile.savingPeriodReminder") : t("profile.periodReminder")}
                </button>
              </div>
            ) : (
              <p className="rounded-xl bg-white/80 px-4 py-3 text-sm leading-5 text-muted">
                {womensHealth.period_start_dates.length
                  ? t("profile.periodEstimateNeedMore")
                  : t("profile.periodEstimateStart")}
              </p>
            )}
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
            <Link href="/assistant?ask=women-cycle" className="btn btn-ghost">
              <Icon name="message" className="h-4 w-4" />
              {t("profile.askLumi")}
            </Link>
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
            <p className="text-xs leading-5 text-muted">{t("profile.pregnancyEstimateNote")}</p>
            <Link href="/assistant?ask=women-pregnancy" className="btn btn-ghost">
              <Icon name="message" className="h-4 w-4" />
              {t("profile.askLumi")}
            </Link>
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
            <p className="text-xs leading-5 text-muted">{t("profile.menopauseFertilityNote")}</p>
            <Link href="/assistant?ask=women-menopause" className="btn btn-ghost">
              <Icon name="message" className="h-4 w-4" />
              {t("profile.askLumi")}
            </Link>
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
            <p className="text-xs leading-5 text-muted">{t("profile.screeningNote")}</p>
            <Link href="/assistant?ask=women-screening" className="btn btn-ghost">
              <Icon name="message" className="h-4 w-4" />
              {t("profile.askLumi")}
            </Link>
          </fieldset>
        )}

        {message && <p role="status" className="text-sm text-ok">{message}</p>}
        {error && <p role="alert" className="text-sm text-crit">{error}</p>}
        <div className="flex justify-end border-t border-line pt-5">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? t("profile.saving") : t("profile.saveWomensHealth")}
          </button>
        </div>
      </form>
    </main>
  );
}
