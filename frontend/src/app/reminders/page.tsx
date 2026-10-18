"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  api,
  ConfirmedPrescriptionSchedule,
  familyApi,
  FamilyMember,
  HealthReminder,
  RoutineSuggestion,
} from "@/api";
import Icon from "@/components/Icon";
import { LANGS, Lang } from "@/i18n";
import { useProfile } from "@/Shell";

const SPEECH_LOCALES: Record<Lang, string> = {
  en: "en-US",
  hi: "hi-IN",
  te: "te-IN",
  ta: "ta-IN",
};

function defaultDueValue() {
  const date = new Date(Date.now() + 60 * 60 * 1000);
  date.setMinutes(0, 0, 0);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export default function RemindersPage() {
  const { t, i18n } = useTranslation();
  const { profile } = useProfile();
  const [reminders, setReminders] = useState<HealthReminder[]>([]);
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [profileOid, setProfileOid] = useState<string | undefined>();
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [dueAt, setDueAt] = useState(defaultDueValue);
  const [category, setCategory] = useState<HealthReminder["category"]>("medication");
  const [recurrence, setRecurrence] = useState<HealthReminder["recurrence"]>("none");
  const [sourceDocumentId, setSourceDocumentId] = useState<number | undefined>();
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("default");
  const [routineSuggestions, setRoutineSuggestions] = useState<RoutineSuggestion[]>([]);
  const [confirmedPrescriptions, setConfirmedPrescriptions] = useState<ConfirmedPrescriptionSchedule[]>([]);
  const [routineNote, setRoutineNote] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [addingSuggestion, setAddingSuggestion] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const notified = useRef(new Set<number>());

  useEffect(() => {
    if ("Notification" in window) setPermission(Notification.permission);
    familyApi.list()
      .then(({ members }) => setFamilyMembers(members))
      .catch(() => setError(t("family.loadError")));
    const requestedProfile = new URLSearchParams(window.location.search).get("profile_oid");
    if (requestedProfile) setProfileOid(requestedProfile);
    const params = new URLSearchParams(window.location.search);
    const requestedTitle = params.get("title");
    const requestedDetails = params.get("details");
    const requestedCategory = params.get("category");
    const requestedDocumentId = Number(params.get("document_id"));
    if (requestedTitle) setTitle(requestedTitle);
    if (requestedDetails) setDetails(requestedDetails);
    if (requestedCategory === "medication" || requestedCategory === "appointment" || requestedCategory === "follow_up" || requestedCategory === "meal" || requestedCategory === "sleep" || requestedCategory === "wellness" || requestedCategory === "other") {
      setCategory(requestedCategory);
    }
    if (Number.isInteger(requestedDocumentId) && requestedDocumentId > 0) setSourceDocumentId(requestedDocumentId);
  }, [t]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.reminders(profileOid, true)
      .then((items) => { if (!cancelled) setReminders(items); })
      .catch(() => { if (!cancelled) setError(t("reminders.loadError")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [profileOid, t]);

  useEffect(() => {
    let cancelled = false;
    setConfirmedPrescriptions([]);
    api.confirmedPrescriptions(profileOid)
      .then((items) => { if (!cancelled) setConfirmedPrescriptions(items); })
      .catch(() => { if (!cancelled) setError(t("reminders.prescriptionsLoadError")); });
    return () => { cancelled = true; };
  }, [profileOid, t]);

  useEffect(() => {
    if (permission !== "granted") return;
    const notifyDue = () => {
      const now = Date.now();
      for (const reminder of reminders) {
        const due = new Date(reminder.due_at).getTime();
        if (reminder.status !== "pending" || due > now || due < now - 60_000 || notified.current.has(reminder.id)) continue;
        new Notification(reminder.title, {
          body: reminder.details || t(`reminders.${reminder.category}`),
          tag: `health-reminder-${reminder.id}`,
        });
        if (profile?.voice_reminders_enabled && "speechSynthesis" in window) {
          const selectedVoiceLanguage = profile.voice_language in LANGS
            ? profile.voice_language as Lang
            : "en";
          const locale = SPEECH_LOCALES[selectedVoiceLanguage];
          const utterance = new SpeechSynthesisUtterance(
            [reminder.spoken_title || reminder.title, reminder.spoken_details || reminder.details]
              .filter(Boolean)
              .join(". "),
          );
          const voices = window.speechSynthesis.getVoices();
          utterance.lang = locale;
          utterance.voice = voices.find((voice) => voice.lang.toLowerCase() === locale.toLowerCase())
            ?? voices.find((voice) => voice.lang.split("-")[0].toLowerCase() === selectedVoiceLanguage)
            ?? null;
          window.speechSynthesis.speak(utterance);
        }
        notified.current.add(reminder.id);
      }
    };
    notifyDue();
    const interval = window.setInterval(notifyDue, 30_000);
    return () => window.clearInterval(interval);
  }, [permission, profile, reminders, t]);

  async function refresh() {
    setReminders(await api.reminders(profileOid, true));
  }

  async function createReminder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      await api.createReminder({
        title,
        details: details || undefined,
        due_at: new Date(dueAt).toISOString(),
        category,
        recurrence,
        ...(sourceDocumentId ? { document_id: sourceDocumentId } : {}),
      }, profileOid);
      setTitle("");
      setDetails("");
      setDueAt(defaultDueValue());
      setRecurrence("none");
      setSourceDocumentId(undefined);
      await refresh();
    } catch {
      setError(t("reminders.saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function updateReminder(reminder: HealthReminder, action: "complete" | "dismiss") {
    setError("");
    try {
      if (action === "complete") {
        await api.completeReminder(reminder.id, profileOid);
        if (reminder.recurrence !== "none") notified.current.delete(reminder.id);
      }
      else await api.updateReminder(reminder.id, { status: "dismissed" }, profileOid);
      await refresh();
    } catch {
      setError(t("reminders.actionError"));
    }
  }

  async function deleteReminder(reminder: HealthReminder) {
    if (!window.confirm(t("reminders.confirmDelete"))) return;
    setError("");
    try {
      await api.deleteReminder(reminder.id, profileOid);
      await refresh();
    } catch {
      setError(t("reminders.actionError"));
    }
  }

  async function enableNotifications() {
    if (!("Notification" in window)) {
      setPermission("unsupported");
      return;
    }
    try {
      setPermission(await Notification.requestPermission());
    } catch {
      setError(t("reminders.permissionError"));
    }
  }

  async function suggestRoutine() {
    setError("");
    setSuggesting(true);
    try {
      const writtenLanguage = i18n.language.split("-")[0];
      const voiceLanguage = profile?.voice_language;
      const result = await api.routineSuggestions({
        written_language: writtenLanguage in LANGS ? writtenLanguage as Lang : "en",
        voice_language: voiceLanguage && voiceLanguage in LANGS ? voiceLanguage as Lang : "en",
      }, profileOid);
      setRoutineSuggestions(result.suggestions);
      setRoutineNote(result.note);
    } catch {
      setError(t("reminders.suggestionsError"));
    } finally {
      setSuggesting(false);
    }
  }

  function dueAtForLocalTime(localTime: string) {
    const [hours, minutes] = localTime.split(":").map(Number);
    const due = new Date();
    due.setHours(hours, minutes, 0, 0);
    if (due.getTime() <= Date.now()) due.setDate(due.getDate() + 1);
    return due.toISOString();
  }

  async function addRoutineReminder(item: RoutineSuggestion, index: number) {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(item.local_time)) return;
    setError("");
    setAddingSuggestion(index);
    try {
      await api.createReminder({
        title: item.title,
        details: item.details,
        spoken_title: item.spoken_title,
        spoken_details: item.spoken_details,
        due_at: dueAtForLocalTime(item.local_time),
        category: item.category,
        recurrence: "daily",
      }, profileOid);
      setRoutineSuggestions((current) => current.filter((_, itemIndex) => itemIndex !== index));
      await refresh();
    } catch {
      setError(t("reminders.saveError"));
    } finally {
      setAddingSuggestion(null);
    }
  }

  function useConfirmedPrescription(item: ConfirmedPrescriptionSchedule) {
    setTitle(item.name + (item.strength ? ` ${item.strength}` : ""));
    setDetails([
      item.dose_pattern ? `${t("reminders.prescriptionDose")}: ${item.dose_pattern}` : "",
      item.timing ? `${t("reminders.prescriptionTiming")}: ${item.timing}` : "",
    ].filter(Boolean).join("\n"));
    setDueAt("");
    setCategory("medication");
    setRecurrence("none");
    setSourceDocumentId(item.document_id);
  }

  const pending = reminders.filter((item) => item.status === "pending");
  const history = reminders.filter((item) => item.status !== "pending");
  const dateTime = (value: string) => new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">{t("nav.reminders")}</p>
          <h1 className="h-display mt-1 text-3xl font-semibold">{t("reminders.title")}</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted">{t("reminders.description")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {familyMembers.length > 0 && (
            <label className="space-y-1 text-xs font-medium text-muted">
              <span>{t("reminders.profileScope")}</span>
              <select value={profileOid ?? ""} onChange={(event) => setProfileOid(event.target.value || undefined)} className="input py-2">
                <option value="">{t("family.myProfile")}</option>
                {familyMembers.map((member) => <option key={member.oid} value={member.oid}>{member.name}</option>)}
              </select>
            </label>
          )}
          {permission === "granted"
            ? <span className="btn btn-soft !min-h-9"><Icon name="bell" className="h-4 w-4" />{t("reminders.notificationsEnabled")}</span>
            : <button type="button" onClick={() => void enableNotifications()} className="btn btn-ghost !min-h-9" disabled={permission === "unsupported" || permission === "denied"}>
              <Icon name="bell" className="h-4 w-4" />
              {permission === "unsupported" ? t("reminders.notificationsUnsupported")
                : permission === "denied" ? t("reminders.notificationsDenied")
                  : t("reminders.enableNotifications")}
            </button>}
        </div>
      </header>

      <p className="rounded-xl bg-brand-soft px-4 py-3 text-xs leading-5 text-muted">{t("reminders.notificationNote")}</p>
      {error && <p role="alert" className="rounded-xl border border-crit/30 bg-crit-soft px-3 py-2 text-sm text-crit">{error}</p>}

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.8fr)]">
        <section className="card space-y-4 p-5 lg:col-span-2">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-ink">{t("reminders.routineTitle")}</h2>
              <p className="mt-1 max-w-3xl text-sm text-muted">{t("reminders.routineDescription")}</p>
            </div>
            <button type="button" onClick={() => void suggestRoutine()} disabled={suggesting} className="btn btn-primary">
              <Icon name="sparkles" className="h-4 w-4" />
              {suggesting ? t("reminders.suggesting") : t("reminders.getSuggestions")}
            </button>
          </div>
          {routineNote && <p className="rounded-lg bg-surface-2 px-3 py-2 text-xs leading-5 text-muted">{routineNote}</p>}
          {routineSuggestions.length > 0 && <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {routineSuggestions.map((item, index) => (
              <li key={`${item.category}-${item.local_time}-${index}`} className="rounded-xl border border-line p-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-ink">{item.title}</p>
                    <label className="mt-1 flex items-center gap-2 text-xs text-muted">
                      <span>{t("reminders.suggestedTime")}</span>
                      <input type="time" value={item.local_time} aria-label={t("reminders.suggestedTime")}
                        onChange={(event) => setRoutineSuggestions((current) => current.map((suggestion, itemIndex) =>
                          itemIndex === index ? { ...suggestion, local_time: event.target.value } : suggestion))}
                        className="input !min-h-8 w-auto px-2 py-1" />
                    </label>
                    <p className="mt-1 text-xs text-muted">{t("reminders.daily")} · {t(`reminders.${item.category}`)}</p>
                  </div>
                  <button type="button" onClick={() => void addRoutineReminder(item, index)}
                    disabled={addingSuggestion !== null || !/^([01]\d|2[0-3]):[0-5]\d$/.test(item.local_time)}
                    className="btn btn-soft !min-h-8 !px-2.5 text-xs">
                    {addingSuggestion === index ? t("reminders.saving") : t("reminders.addSuggestion")}
                  </button>
                </div>
                <p className="mt-2 text-sm text-muted">{item.details}</p>
              </li>
            ))}
          </ul>}
          {confirmedPrescriptions.length > 0 && <div className="border-t border-line pt-4">
            <h3 className="text-sm font-semibold text-ink">{t("reminders.confirmedPrescriptions")}</h3>
            <p className="mt-1 text-xs text-muted">{t("reminders.prescriptionReminderNote")}</p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {confirmedPrescriptions.map((item) => (
                <li key={`${item.document_id}-${item.name}`} className="flex items-center justify-between gap-3 rounded-lg bg-surface-2 p-3">
                  <div className="min-w-0">
                    <p className="font-medium">{item.name}{item.strength ? ` · ${item.strength}` : ""}</p>
                    {(item.dose_pattern || item.timing) && <p className="mt-1 text-xs text-muted">
                      {[item.dose_pattern, item.timing].filter(Boolean).join(" · ")}
                    </p>}
                  </div>
                  {item.dose_pattern || item.timing
                    ? <button type="button" onClick={() => useConfirmedPrescription(item)} className="btn btn-ghost !min-h-8 shrink-0 !px-2.5 text-xs">
                        {t("reminders.usePrescription")}
                      </button>
                    : <span className="text-xs text-muted">{t("reminders.noRecordedSchedule")}</span>}
                </li>
              ))}
            </ul>
          </div>}
        </section>
        <section className="card space-y-4 p-5">
          <h2 className="font-semibold text-ink">{t("reminders.newReminder")}</h2>
          <form onSubmit={(event) => void createReminder(event)} className="space-y-3">
            <label className="block space-y-1 text-sm font-medium">
              {t("reminders.titleLabel")}
              <input value={title} onChange={(event) => setTitle(event.target.value)} required maxLength={160} className="input w-full" />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              {t("reminders.detailsLabel")}
              <textarea value={details} onChange={(event) => setDetails(event.target.value)} maxLength={2000} rows={2} className="input w-full resize-y" />
            </label>
            <label className="block space-y-1 text-sm font-medium">
              {t("reminders.dueLabel")}
              <input type="datetime-local" value={dueAt} onChange={(event) => setDueAt(event.target.value)} required className="input w-full" />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block space-y-1 text-sm font-medium">
                {t("reminders.categoryLabel")}
                <select value={category} onChange={(event) => setCategory(event.target.value as HealthReminder["category"])} className="input w-full">
                  {(["medication", "appointment", "follow_up", "meal", "sleep", "wellness", "other"] as const).map((value) => <option key={value} value={value}>{t(`reminders.${value}`)}</option>)}
                </select>
              </label>
              <label className="block space-y-1 text-sm font-medium">
                {t("reminders.recurrenceLabel")}
                <select value={recurrence} onChange={(event) => setRecurrence(event.target.value as HealthReminder["recurrence"])} className="input w-full">
                  {(["none", "daily", "weekly", "monthly"] as const).map((value) => <option key={value} value={value}>{t(`reminders.${value}`)}</option>)}
                </select>
              </label>
            </div>
            <button type="submit" disabled={saving || !title.trim() || !dueAt} className="btn btn-primary">
              <Icon name="plus" className="h-4 w-4" />              {saving ? t("reminders.saving") : t("reminders.save")}
            </button>
          </form>
        </section>

        <div className="space-y-5">
          <section className="card space-y-3 p-5">
            <h2 className="font-semibold text-ink">{t("reminders.upcoming")}</h2>
            {loading ? <p role="status" className="text-sm text-muted">{t("auth.checking")}</p>
              : pending.length === 0 ? <p className="text-sm text-muted">{t("reminders.noReminders")}</p>
                : <ul className="space-y-3">{pending.map((item) => {
                  const overdue = new Date(item.due_at).getTime() < Date.now();
                  return <li key={item.id} className="rounded-xl border border-line p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium text-ink">{item.title}</p>
                        <p className="mt-1 text-xs text-muted">{dateTime(item.due_at)} · {t(`reminders.${item.category}`)} · {t(`reminders.${item.recurrence}`)}</p>
                        {item.details && <p className="mt-2 whitespace-pre-wrap text-sm text-muted">{item.details}</p>}
                      </div>
                      {overdue && <span className="rounded-full bg-high-soft px-2 py-1 text-[11px] font-semibold text-high">{t("reminders.overdue")}</span>}
                    </div>
                    <div className="mt-3 flex gap-2">
                      <button type="button" onClick={() => void updateReminder(item, "complete")} className="btn btn-soft !min-h-8 !px-2.5 text-xs">{t("reminders.complete")}</button>
                      <button type="button" onClick={() => void updateReminder(item, "dismiss")} className="btn btn-ghost !min-h-8 !px-2.5 text-xs">{t("reminders.dismiss")}</button>
                      <button type="button" onClick={() => void deleteReminder(item)} className="btn btn-ghost !min-h-8 !px-2.5 text-xs text-crit">{t("reminders.delete")}</button>
                    </div>
                  </li>;
                })}</ul>}
          </section>
          {history.length > 0 && <section className="card space-y-3 p-5">
            <h2 className="font-semibold text-ink">{t("reminders.history")}</h2>
            <ul className="space-y-2">{history.map((item) => (
              <li key={item.id} className="rounded-lg bg-surface-2 px-3 py-2 text-sm">
                <span className="font-medium">{item.title}</span><span className="ml-2 text-xs text-muted">{dateTime(item.due_at)} · {t(`reminders.${item.status}`)}</span>
              </li>
            ))}</ul>
          </section>}
        </div>
      </div>
    </div>
  );
}
