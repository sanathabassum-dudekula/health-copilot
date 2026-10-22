"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiRequestError, familyApi, FamilyMember, Profile } from "@/api";
import Icon from "@/components/Icon";
import VitalsPanel from "@/components/VitalsPanel";

export default function DevicesPage() {
  const { t } = useTranslation();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [selectedOid, setSelectedOid] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const linkedProfiles = api.authMe()
      .then(() => familyApi.list())
      .catch((loadError) => {
        if (loadError instanceof ApiRequestError && loadError.status === 401) {
          return { members: [] as FamilyMember[] };
        }
        throw loadError;
      });
    Promise.all([api.profile(), linkedProfiles])
      .then(([mainProfile, linked]) => {
        if (cancelled) return;
        setProfile(mainProfile);
        setMembers(linked.members);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : t("wearables.profileLoadError"));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [t]);

  return (
    <div className="space-y-6">
      <header>
        <p className="eyebrow">{t("nav.devices")}</p>
        <h1 className="h-display mt-1 text-3xl font-semibold">{t("wearables.pageTitle")}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{t("wearables.pageDescription")}</p>
      </header>

      {error && <p role="alert" className="rounded-xl border border-crit/30 bg-crit-soft px-3 py-2 text-sm text-crit">{error}</p>}

      <section className="card flex flex-wrap items-center gap-3 p-4">
        <Icon name="user" className="text-brand" />
        <label className="min-w-56 flex-1 space-y-1 text-sm font-medium">
          {t("wearables.profile")}
          <select
            className="input w-full"
            value={selectedOid}
            onChange={(event) => setSelectedOid(event.target.value)}
            disabled={loading || !profile}
          >
            {profile && <option value="">{profile.name || t("home.myProfile")}</option>}
            {members.map((member) => <option key={member.oid} value={member.oid}>{member.name}</option>)}
          </select>
        </label>
      </section>

      {loading ? <div className="card p-5 text-sm text-muted">{t("wearables.loading")}</div>
        : profile && <VitalsPanel key={selectedOid || "main"} profileOid={selectedOid || undefined} />}
    </div>
  );
}
