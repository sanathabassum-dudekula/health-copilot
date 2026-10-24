"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, Profile } from "@/api";
import VitalsPanel from "@/components/VitalsPanel";

export default function DevicesPage() {
  const { t } = useTranslation();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    api.profile()
      .then((mainProfile) => {
        if (!cancelled) setProfile(mainProfile);
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : t("wearables.profileLoadError")
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <div className="space-y-6">
      <header>
        <p className="eyebrow">{t("nav.devices")}</p>
        <h1 className="h-display mt-1 text-3xl font-semibold">
          {t("wearables.pageTitle")}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
          {t("wearables.pageDescription")}
        </p>
      </header>

      {error && (
        <p
          role="alert"
          className="rounded-xl border border-crit/30 bg-crit-soft px-3 py-2 text-sm text-crit"
        >
          {error}
        </p>
      )}

      {loading ? (
        <div className="card p-5 text-sm text-muted">
          {t("wearables.loading")}
        </div>
      ) : profile ? (
        <VitalsPanel profileOid={profile.oid} />
      ) : null}
    </div>
  );
}