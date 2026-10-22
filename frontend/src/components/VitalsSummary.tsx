"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { api, VitalMetric, VitalSign } from "@/api";
import Icon from "@/components/Icon";

const METRICS: VitalMetric[] = ["heart_rate", "oxygen_saturation", "body_temperature"];

export default function VitalsSummary() {
  const { t, i18n } = useTranslation();
  const [readings, setReadings] = useState<VitalSign[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.vitals()
      .then((items) => { if (!cancelled) setReadings(items); })
      .catch((loadError) => {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : t("wearables.loadError"));
      });
    return () => { cancelled = true; };
  }, [t]);

  const date = (value: string) => new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));

  return (
    <section className="card space-y-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-soft text-brand"><Icon name="activity" /></span>
          <div>
            <h2 className="font-semibold">{t("wearables.summaryTitle")}</h2>
            <p className="text-sm text-muted">{t("wearables.summaryDescription")}</p>
          </div>
        </div>
        <Link href="/devices" className="btn btn-ghost !min-h-9 !px-3 text-sm">
          <Icon name="link" className="h-4 w-4" />{t("wearables.manage")}
        </Link>
      </div>

      {error ? <p role="alert" className="text-sm text-crit">{error}</p>
        : readings === null ? <p className="text-sm text-muted">{t("wearables.loading")}</p>
          : readings.length === 0 ? <p className="text-sm text-muted">{t("wearables.noSummary")}</p>
            : <div className="grid gap-3 sm:grid-cols-3">
              {METRICS.map((metric) => {
                const reading = readings.find((item) => item.metric === metric);
                return (
                  <div key={metric} className="rounded-xl bg-surface-2 p-3">
                    <p className="text-xs font-medium text-muted">{t(`wearables.${metric}`)}</p>
                    <p className="mt-1 text-lg font-semibold tabular-nums">
                      {reading
                        ? <>{reading.value} <span className="text-sm font-medium text-muted">{reading.unit}</span></>
                        : <span className="text-sm font-medium text-muted">{t("wearables.notRecorded")}</span>}
                    </p>
                    {reading && <p className="mt-1 text-xs text-muted">{date(reading.captured_at)}</p>}
                  </div>
                );
              })}
            </div>}
    </section>
  );
}
