"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useTranslation } from "react-i18next";
import { api, Profile } from "@/api";
import { useProfile } from "@/Shell";
import { LANGS, Lang } from "@/i18n";

export default function ProfilePage() {
  const { t, i18n } = useTranslation();
  const { profile, reload } = useProfile();

  const [name, setName] = useState("");
  const [dob, setDob] = useState("");
  const [sex, setSex] = useState("");
  const [language, setLanguage] = useState<Lang>("en");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!profile) return;
    setName(profile.name || "");
    setDob(profile.dob || "");
    setSex(profile.sex || "");
    setLanguage((profile.language in LANGS ? profile.language : "en") as Lang);
  }, [profile]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setError("");

    if (!name.trim()) {
      setError("Please enter your name before saving.");
      return;
    }

    setSaving(true);

    try {
      const payload: {
        name: string;
        sex?: string;
        dob?: string;
        preferred_language: string;
      } = {
        name: name.trim(),
        preferred_language: language,
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
      api.setLanguage(language).catch(() => {});
      reload();
      setMessage(t("profile.saved"));
    } catch {
      setError(t("profile.error"));
    } finally {
      setSaving(false);
    }
  }

  const countCards = [
    { label: t("profile.conditions"), count: profile?.conditions?.length ?? 0 },
    { label: t("profile.medications"), count: profile?.current_medicines?.length ?? 0 },
    { label: t("profile.allergies"), count: profile?.allergies?.length ?? 0 },
  ];

  return (
    <main className="mx-auto w-full max-w-5xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Image src="/curamind-logo.jpeg" alt="CuraMind logo" width={520} height={180} className="h-auto w-[145px] max-w-full object-contain sm:w-[175px]" />
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
                i18n.changeLanguage(next);
                try { localStorage.setItem("lang", next); } catch {}
                api.setLanguage(next).catch(() => {});
              }}
            >
              {(Object.keys(LANGS) as Lang[]).map((key) => (
                <option key={key} value={key}>{LANGS[key]}</option>
              ))}
            </select>
          </label>
          <Link href="/" className="btn btn-ghost border border-[#B9DED5] bg-white text-[#123C46]">{t("profile.switchProfile")}</Link>
        </div>
        <div className="w-full">
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">{t("profile.title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">{t("profile.subtitle")}</p>
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
          </div>

          {message && <p role="status" className="text-sm text-ok">{message}</p>}
          {error && <p role="alert" className="text-sm text-crit">{error}</p>}

          <div className="flex justify-end border-t border-line pt-5">
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? t("profile.saving") : t("profile.save")}
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
            <p className="mt-2 break-all font-medium">{profile?.abha.number || "Not added"}</p>
          </div>
          <div className="rounded-xl border border-line p-4">
            <p className="text-sm text-muted">{t("profile.abhaAddress")}</p>
            <p className="mt-2 break-all font-medium">{profile?.abha.address || "Not added"}</p>
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
