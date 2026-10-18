"use client";

import { FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, AssistantReminderProposal as ReminderProposalData } from "@/api";

function localDateTime(value: string): string {
  if (!value.endsWith("Z") && !/[+-]\d{2}:\d{2}$/.test(value)) {
    return value.slice(0, 16);
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}

export default function AssistantReminderProposal({
  proposal,
  profileOid,
}: {
  proposal: ReminderProposalData;
  profileOid?: string;
}) {
  const { t } = useTranslation();
  const [title, setTitle] = useState(proposal.title);
  const [details, setDetails] = useState(proposal.details ?? "");
  const [dueAt, setDueAt] = useState(() => localDateTime(proposal.due_at));
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  async function saveReminder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dueAt || saving) return;
    setSaving(true);
    setError("");
    try {
      await api.createReminder({
        title,
        details: details || undefined,
        due_at: new Date(dueAt).toISOString(),
        category: proposal.category,
        recurrence: "none",
        ...(proposal.document_id ? { document_id: proposal.document_id } : {}),
      }, profileOid);
      setSaved(true);
    } catch {
      setError(t("reminders.saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-3 rounded-xl border border-brand/30 bg-brand-soft p-3">
      <p className="mb-2 text-xs font-semibold text-brand-strong">{t("assistant.reminderProposalTitle")}</p>
      {saved ? (
        <p role="status" className="text-sm font-medium text-ok">{t("assistant.reminderSaved")}</p>
      ) : (
        <form onSubmit={(event) => void saveReminder(event)} className="space-y-2">
          <label className="block space-y-1 text-xs font-medium text-ink">
            {t("reminders.titleLabel")}
            <input value={title} onChange={(event) => setTitle(event.target.value)}
              required maxLength={160} className="input w-full bg-surface" />
          </label>
          <label className="block space-y-1 text-xs font-medium text-ink">
            {t("reminders.detailsLabel")}
            <textarea value={details} onChange={(event) => setDetails(event.target.value)}
              maxLength={2000} rows={2} className="input w-full resize-y bg-surface" />
          </label>
          <label className="block space-y-1 text-xs font-medium text-ink">
            {t("reminders.dueLabel")}
            <input type="datetime-local" value={dueAt}
              onChange={(event) => setDueAt(event.target.value)}
              required className="input w-full bg-surface" />
          </label>
          {error && <p role="alert" className="text-xs text-crit">{error}</p>}
          <button type="submit" disabled={saving || !title.trim() || !dueAt}
            className="btn btn-primary !min-h-8 !px-3 text-xs">
            {saving ? t("reminders.saving") : t("reminders.save")}
          </button>
        </form>
      )}
    </section>
  );
}
