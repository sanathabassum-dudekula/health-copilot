"use client";

import { FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import QRCode from "qrcode";
import { api, ApiRequestError } from "@/api";
import Icon from "@/components/Icon";
import { useProfile } from "@/Shell";

const QR_SIZE = 640;

export default function EmergencyCardPage() {
  const { t } = useTranslation();
  const { profile, reload } = useProfile();
  const [bloodGroup, setBloodGroup] = useState(profile?.blood_group ?? "");
  const [severeAllergies, setSevereAllergies] = useState(profile?.allergies_text ?? "");
  const [contactName, setContactName] = useState(profile?.emergency_contact_name ?? "");
  const [contactPhone, setContactPhone] = useState(profile?.emergency_contact_phone ?? "");
  const [consent, setConsent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [qrImage, setQrImage] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!profile) return;
    setBloodGroup(profile.blood_group ?? "");
    setSevereAllergies(profile.allergies_text ?? "");
    setContactName(profile.emergency_contact_name ?? "");
    setContactPhone(profile.emergency_contact_phone ?? "");
    setQrImage("");
  }, [
    profile?.oid,
    profile?.blood_group,
    profile?.allergies_text,
    profile?.emergency_contact_name,
    profile?.emergency_contact_phone,
  ]);

  async function saveCard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSaving(true);
    try {
      await api.updateProfile({
        blood_group: bloodGroup.trim() || null,
        allergies_text: severeAllergies.trim() || null,
        emergency_contact_name: contactName.trim() || null,
        emergency_contact_phone: contactPhone.trim() || null,
      });
      await reload();
      setNotice(t("emergency.saved"));
    } catch (saveError) {
      setError(
        saveError instanceof ApiRequestError
          ? saveError.message
          : t("emergency.saveError"),
      );
    } finally {
      setSaving(false);
    }
  }

  async function createQr() {
    setError("");
    setNotice("");
    if (!profile?.name.trim()) {
      setError(t("emergency.nameRequired"));
      return;
    }
    if (!consent) {
      setError(t("emergency.consentRequired"));
      return;
    }
    const text = [
      "CURAMIND EMERGENCY HEALTH CARD",
      `Name: ${profile.name.trim().slice(0, 120)}`,
      `Blood group: ${bloodGroup.trim().slice(0, 40) || "Not provided"}`,
      `Severe allergies: ${severeAllergies.trim().slice(0, 240) || "Not provided"}`,
      `Emergency contact: ${contactName.trim().slice(0, 120) || "Not provided"}`,
      `Contact phone: ${contactPhone.trim().slice(0, 40) || "Not provided"}`,
      `Card created: ${new Date().toISOString().slice(0, 10)}`,
      "User-provided information; verify with the person or clinician.",
    ].join("\n");
    try {
      const image = await QRCode.toDataURL(text, {
        errorCorrectionLevel: "M",
        margin: 3,
        width: QR_SIZE,
        color: { dark: "#123C46", light: "#FFFFFF" },
      });
      setQrImage(image);
    } catch (qrError) {
      console.error("Emergency QR generation failed", qrError);
      setError(t("emergency.qrError"));
    }
  }

  return (
    <main className="mx-auto max-w-4xl space-y-6">
      <header className="no-print relative overflow-hidden rounded-3xl border border-line bg-gradient-to-br from-rose-50 via-white to-brand-soft p-6 shadow-card sm:p-8">
        <div className="relative z-10 max-w-2xl">
          <p className="eyebrow flex items-center gap-2 text-crit">
            <Icon name="shield" className="h-4 w-4" />
            {t("emergency.eyebrow")}
          </p>
          <h1 className="h-display mt-2 text-3xl font-semibold text-ink sm:text-4xl">
            {t("emergency.title")}
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted sm:text-base">
            {t("emergency.description")}
          </p>
        </div>
        <div className="absolute -right-10 -top-10 grid h-48 w-48 place-items-center rounded-full bg-rose-100/70 text-crit/70">
          <Icon name="emergency" className="h-24 w-24" />
        </div>
      </header>

      <section className="no-print grid gap-4 sm:grid-cols-3" aria-label={t("emergency.cardPreview")}>
        {[
          { label: t("emergency.bloodGroup"), value: bloodGroup || t("profile.notSet") },
          { label: t("emergency.severeAllergies"), value: severeAllergies || t("profile.notSet") },
          {
            label: t("emergency.contact"),
            value: contactName || contactPhone || t("profile.notSet"),
          },
        ].map((item) => (
          <article key={item.label} className="card min-w-0 border-t-2 border-t-crit/40 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">{item.label}</p>
            <p className="mt-2 break-words text-sm font-semibold text-ink">{item.value}</p>
          </article>
        ))}
      </section>

      <form onSubmit={(event) => void saveCard(event)} className="no-print card space-y-5 p-5 sm:p-7">
        <div>
          <h2 className="text-lg font-semibold text-ink">{t("emergency.editTitle")}</h2>
          <p className="mt-1 text-sm text-muted">{t("emergency.editDescription")}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm font-medium">
            {t("emergency.bloodGroup")}
            <input
              className="input mt-1 w-full"
              value={bloodGroup}
              onChange={(event) => {
                setBloodGroup(event.target.value);
                setQrImage("");
              }}
              maxLength={40}
              autoComplete="off"
            />
          </label>
          <label className="block text-sm font-medium">
            {t("emergency.severeAllergies")}
            <textarea
              className="input mt-1 w-full"
              value={severeAllergies}
              onChange={(event) => {
                setSevereAllergies(event.target.value);
                setQrImage("");
              }}
              maxLength={240}
              rows={2}
            />
          </label>
          <label className="block text-sm font-medium">
            {t("emergency.contactName")}
            <input
              className="input mt-1 w-full"
              value={contactName}
              onChange={(event) => {
                setContactName(event.target.value);
                setQrImage("");
              }}
              maxLength={120}
              autoComplete="off"
            />
          </label>
          <label className="block text-sm font-medium">
            {t("emergency.contactPhone")}
            <input
              className="input mt-1 w-full"
              value={contactPhone}
              onChange={(event) => {
                setContactPhone(event.target.value);
                setQrImage("");
              }}
              maxLength={40}
              type="tel"
              autoComplete="tel"
            />
          </label>
        </div>

        {error && <p role="alert" className="rounded-xl border border-crit/30 bg-crit-soft px-3 py-2 text-sm text-crit">{error}</p>}
        {notice && <p role="status" className="text-sm text-ok">{notice}</p>}

        <label className="flex items-start gap-3 rounded-xl border border-crit/30 bg-crit-soft p-3 text-sm">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => {
              setConsent(event.target.checked);
              if (!event.target.checked) setQrImage("");
            }}
            className="mt-1"
          />
          <span>{t("emergency.consent")}</span>
        </label>
        <div className="flex flex-wrap gap-3 border-t border-line pt-4">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Icon name="check" className="h-4 w-4" />
            {saving ? t("emergency.saving") : t("emergency.save")}
          </button>
          <button type="button" onClick={() => void createQr()} className="btn btn-soft">
            <Icon name="image" className="h-4 w-4" />
            {t("emergency.generateQr")}
          </button>
        </div>
      </form>

      <section className="no-print rounded-2xl border border-high/30 bg-high-soft p-4 text-sm leading-6 text-ink">
        <p className="font-semibold">{t("emergency.privacyTitle")}</p>
        <p className="mt-1">{t("emergency.privacyDescription")}</p>
      </section>

      {qrImage && (
        <section className="card grid gap-5 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:p-7">
          <div>
            <h2 className="text-lg font-semibold text-ink">{t("emergency.qrReady")}</h2>
            <p className="mt-2 text-sm leading-6 text-muted">{t("emergency.qrInstructions")}</p>
            <div className="no-print mt-4 flex flex-wrap gap-2">
              <a
                href={qrImage}
                download="curamind-emergency-card.png"
                onClick={(event) => {
                  if (!consent) {
                    event.preventDefault();
                    setError(t("emergency.consentRequired"));
                  }
                }}
                className={`btn ${consent ? "btn-primary" : "btn-soft"}`}
              >
                <Icon name="download" className="h-4 w-4" />
                {t("emergency.downloadQr")}
              </a>
              <button type="button" onClick={() => window.print()} className="btn btn-ghost">
                <Icon name="printer" className="h-4 w-4" />
                {t("emergency.printQr")}
              </button>
            </div>
          </div>
          <img
            src={qrImage}
            alt={t("emergency.qrAlt")}
            width={QR_SIZE}
            height={QR_SIZE}
            className="mx-auto w-56 rounded-xl border border-line bg-white p-2 sm:w-64"
          />
        </section>
      )}
    </main>
  );
}
