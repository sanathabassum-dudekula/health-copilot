"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { api, HealthInsights } from "@/api";
import Icon from "@/components/Icon";

export default function HealthInsightsPanel({ profileOid }: { profileOid?: string }) {
  const { t, i18n } = useTranslation();
  const [insights, setInsights] = useState<HealthInsights | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    setInsights(null);
    api.insights(profileOid)
      .then((result) => { if (!cancelled) setInsights(result); })
      .catch(() => { if (!cancelled) setError(t("insights.loadError")); });
    return () => { cancelled = true; };
  }, [profileOid, t]);

  const dateLabel = (value: string | null) => value
    ? new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium" }).format(new Date(value))
    : t("none");
  const shownValue = (value: string | number | null, unit: string | null) =>
    [value, unit].filter((part) => part !== null && part !== "").join(" ");

  return (
    <section className="space-y-4">
      <header>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="eyebrow">{t("insights.title")}</p>
            <p className="mt-1 text-sm text-muted">{t("insights.description")}</p>
          </div>
          <Link href={`/assistant${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`} className="btn btn-ghost !min-h-9 !px-3 text-xs">
            <Icon name="message" className="h-4 w-4" />{t("insights.openChat")}
          </Link>
        </div>
      </header>
      {error && <p role="alert" className="rounded-xl bg-crit-soft px-3 py-2 text-sm text-crit">{error}</p>}
      {!insights ? <p role="status" className="card p-4 text-sm text-muted">{t("auth.checking")}</p> : (
        <>
          <div className="grid gap-4 xl:grid-cols-2">
            <section className="card space-y-3 p-4">
              <h2 className="font-semibold text-ink">{t("insights.results")}</h2>
              {insights.flagged_results.length === 0
                ? <p className="text-sm text-muted">{t("insights.noResults")}</p>
                : <ul className="space-y-2">{insights.flagged_results.map((item, index) => (
                  <li key={`${item.document_id}-${item.test}-${index}`} className="flex items-start justify-between gap-3 rounded-xl bg-surface-2 p-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.test}</p>
                      <p className="text-xs text-muted">{dateLabel(item.date)}</p>
                    </div>
                    <Link href={`/documents/${item.document_id}`} className="shrink-0 text-sm font-semibold text-brand hover:underline">
                      {shownValue(item.value, item.unit)}
                    </Link>
                  </li>
                ))}</ul>}
            </section>
            <section className="card space-y-3 p-4">
              <h2 className="font-semibold text-ink">{t("insights.trends")}</h2>
              {insights.trends.length === 0
                ? <p className="text-sm text-muted">{t("insights.noTrends")}</p>
                : <ul className="space-y-2">{insights.trends.map((item) => (
                  <li key={`${item.document_id}-${item.test}`} className="rounded-xl bg-surface-2 p-3">
                    <p className="text-sm font-medium">{item.test}</p>
                    <p className="mt-1 text-xs text-muted">
                      {t("insights.previous")}: {shownValue(item.previous_value, item.unit)} ({dateLabel(item.previous_date)})
                    </p>
                    <p className="text-xs text-muted">
                      {t("insights.latest")}: {shownValue(item.latest_value, item.unit)} ({dateLabel(item.latest_date)})
                      {" · "}{t(`insights.${item.direction}`)}
                    </p>
                  </li>
                ))}</ul>}
            </section>
          </div>
          <section className="card space-y-3 p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-semibold text-ink">{t("insights.followUps")}</h2>
              <Link href={`/reminders${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`} className="btn btn-ghost !min-h-8 !px-2.5 text-xs">
                <Icon name="bell" className="h-4 w-4" />{t("reminders.newReminder")}
              </Link>
            </div>
            {insights.follow_ups.length === 0
              ? <p className="text-sm text-muted">{t("insights.noFollowUps")}</p>
              : <ul className="space-y-2">{insights.follow_ups.map((item, index) => (
                <li key={`${index}-${item}`} className="flex items-start justify-between gap-3 rounded-xl bg-surface-2 p-3">
                  <span className="text-sm text-ink">{item}</span>
                  <Link href={`/reminders?${new URLSearchParams({
                    ...(profileOid ? { profile_oid: profileOid } : {}),
                    title: t("insights.followUpReminderTitle"),
                    details: item,
                    category: "follow_up",
                  }).toString()}`} className="shrink-0 text-xs font-semibold text-brand hover:underline">
                    {t("reminders.newReminder")}
                  </Link>
                </li>
              ))}</ul>}
            <p className="text-xs leading-5 text-muted">{t("insights.followUpSourceNote")}</p>
          </section>
          {insights.medicine_reminder_suggestions.length > 0 && (
            <section className="card space-y-3 p-4">
              <h2 className="font-semibold text-ink">{t("insights.medicineReminderSuggestions")}</h2>
              <p className="text-xs text-muted">{t("insights.medicineReminderNote")}</p>
              <ul className="divide-y divide-line">{insights.medicine_reminder_suggestions.map((medicine) => {
                const details = [
                  medicine.dose_pattern,
                  medicine.timing,
                  t("insights.verifyPrescriptionSchedule"),
                ].filter(Boolean).join(" · ");
                const query = new URLSearchParams({
                  ...(profileOid ? { profile_oid: profileOid } : {}),
                  title: medicine.name,
                  details,
                  category: "medication",
                  document_id: String(medicine.document_id),
                });
                return <li key={`${medicine.document_id}-${medicine.name}`} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{medicine.name}</p>
                    <p className="truncate text-xs text-muted">{[medicine.dose_pattern, medicine.timing].filter(Boolean).join(" · ")}</p>
                  </div>
                  <Link href={`/reminders?${query.toString()}`} className="shrink-0 text-xs font-semibold text-brand hover:underline">{t("reminders.newReminder")}</Link>
                </li>;
              })}</ul>
            </section>
          )}
          <section className="card space-y-3 p-4">
            <h2 className="font-semibold text-ink">{t("insights.wellness")}</h2>
            <ul className="grid gap-3 md:grid-cols-2">{insights.wellness.map((item, index) => (
              <li key={`${item.kind}-${index}`} className="rounded-xl bg-brand-soft p-3">
                <p className="text-sm font-semibold text-ink">{t(`insights.${item.kind}.title`)}</p>
                <p className="mt-1 text-sm leading-5 text-muted">{t(`insights.${item.kind}.detail`)}</p>
              </li>
            ))}</ul>
          </section>
          <p className="text-xs leading-5 text-muted">{t("insights.limitations")}</p>
        </>
      )}
    </section>
  );
}
