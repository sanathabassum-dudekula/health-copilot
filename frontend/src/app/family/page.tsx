"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { api, Doc, familyApi, FamilyMember, FamilyMemberFields } from "@/api";
import HealthInsightsPanel from "@/components/HealthInsightsPanel";
import Icon from "@/components/Icon";
import { fmtDate } from "@/components/ui";

type MemberForm = {
  name: string;
  dob: string;
  sex: string;
  age: string;
  blood_group: string;
  allergies_text: string;
  conditions_text: string;
  medicines_text: string;
};

const EMPTY_FORM: MemberForm = {
  name: "",
  dob: "",
  sex: "",
  age: "",
  blood_group: "",
  allergies_text: "",
  conditions_text: "",
  medicines_text: "",
};

function memberForm(member?: FamilyMember): MemberForm {
  return member ? {
    name: member.name,
    dob: member.dob ?? "",
    sex: member.sex ?? "",
    age: member.age?.toString() ?? "",
    blood_group: member.blood_group ?? "",
    allergies_text: member.allergies_text ?? "",
    conditions_text: member.conditions_text ?? "",
    medicines_text: member.medicines_text ?? "",
  } : EMPTY_FORM;
}

function memberPayload(form: MemberForm): FamilyMemberFields {
  return {
    name: form.name.trim(),
    dob: form.dob || null,
    sex: form.sex || null,
    age: form.age ? Number(form.age) : null,
    blood_group: form.blood_group || null,
    allergies_text: form.allergies_text || null,
    conditions_text: form.conditions_text || null,
    medicines_text: form.medicines_text || null,
  };
}

export default function FamilyPage() {
  const { t, i18n } = useTranslation();
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [selectedOid, setSelectedOid] = useState("");
  const [form, setForm] = useState<MemberForm>(EMPTY_FORM);
  const [documents, setDocuments] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  async function loadMembers(selectOid?: string) {
    const response = await familyApi.list();
    setMembers(response.members);
    const nextOid = selectOid ?? (response.members.some((member) => member.oid === selectedOid)
      ? selectedOid
      : response.members[0]?.oid ?? "");
    setSelectedOid(nextOid);
    const selected = response.members.find((member) => member.oid === nextOid);
    setForm(memberForm(selected));
  }

  useEffect(() => {
    let cancelled = false;
    familyApi.list()
      .then(({ members: loaded }) => {
        if (cancelled) return;
        setMembers(loaded);
        if (loaded[0]) {
          setSelectedOid(loaded[0].oid);
          setForm(memberForm(loaded[0]));
        }
      })
      .catch(() => { if (!cancelled) setError(t("family.loadError")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [t]);

  useEffect(() => {
    let cancelled = false;
    setDocuments([]);
    if (!selectedOid) return () => { cancelled = true; };
    api.docs(selectedOid)
      .then((items) => { if (!cancelled) setDocuments(items); })
      .catch(() => { if (!cancelled) setError(t("family.loadError")); });
    const interval = window.setInterval(() => {
      if (!cancelled) {
        api.docs(selectedOid)
          .then((items) => { if (!cancelled) setDocuments(items); })
          .catch(() => { if (!cancelled) setError(t("family.loadError")); });
      }
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [selectedOid, t]);

  async function saveMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const payload = memberPayload(form);
      const saved = selectedOid
        ? await familyApi.update(selectedOid, payload)
        : await familyApi.add(payload);
      await loadMembers(saved.oid);
    } catch {
      setError(t("family.saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function removeMember() {
    const member = members.find((item) => item.oid === selectedOid);
    if (!member || !window.confirm(t("family.confirmRemove"))) return;
    setError("");
    try {
      await familyApi.remove(member.oid);
      setSelectedOid("");
      setForm(EMPTY_FORM);
      await loadMembers("");
    } catch {
      setError(t("family.removeError"));
    }
  }

  async function uploadDocument(file: File | undefined) {
    if (!file || !selectedOid) return;
    setUploading(true);
    setError("");
    try {
      const document = await api.upload(file, selectedOid);
      setDocuments((current) => [document, ...current]);
    } catch {
      setError(t("family.uploadFailed"));
    } finally {
      setUploading(false);
    }
  }

  const selected = members.find((member) => member.oid === selectedOid);
  const update = (field: keyof MemberForm, value: string) => setForm((current) => ({ ...current, [field]: value }));

  return (
    <div className="space-y-6">
      <header>
        <p className="eyebrow">{t("nav.family")}</p>
        <h1 className="h-display mt-1 text-3xl font-semibold">{t("family.title")}</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted">{t("family.description")}</p>
      </header>
      {error && <p role="alert" className="rounded-xl border border-crit/30 bg-crit-soft px-3 py-2 text-sm text-crit">{error}</p>}

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(17rem,0.7fr)_minmax(0,1.3fr)]">
        <section className="card space-y-4 p-4">
          <label className="block space-y-1 text-sm font-medium">
            {t("family.profileScope")}
            <select value={selectedOid} onChange={(event) => {
              const next = members.find((member) => member.oid === event.target.value);
              setSelectedOid(event.target.value);
              setForm(memberForm(next));
            }} className="input w-full" disabled={loading || members.length === 0}>
              {members.length === 0 ? <option value="">{t("family.noMembers")}</option>
                : members.map((member) => <option key={member.oid} value={member.oid}>{member.name}</option>)}
            </select>
          </label>
          <button type="button" onClick={() => { setSelectedOid(""); setForm(EMPTY_FORM); setDocuments([]); setError(""); }}
            className="btn btn-ghost w-full justify-center">
            <Icon name="plus" className="h-4 w-4" />{t("family.addMember")}
          </button>
          {members.length === 0 && !loading && <p className="text-sm text-muted">{t("family.noMembers")}</p>}

          <form onSubmit={(event) => void saveMember(event)} className="space-y-3 border-t border-line pt-4">
            <h2 className="font-semibold text-ink">{selected ? t("family.editMember") : t("family.addMember")}</h2>
            <label className="block space-y-1 text-sm font-medium">{t("family.name")}
              <input value={form.name} onChange={(event) => update("name", event.target.value)} required maxLength={120} className="input w-full" />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block space-y-1 text-sm font-medium">{t("family.dob")}
                <input type="date" value={form.dob} onChange={(event) => update("dob", event.target.value)} className="input w-full" />
              </label>
              <label className="block space-y-1 text-sm font-medium">{t("family.age")}
                <input type="number" min={0} max={130} value={form.age} onChange={(event) => update("age", event.target.value)} className="input w-full" />
              </label>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block space-y-1 text-sm font-medium">{t("family.sex")}
                <input value={form.sex} onChange={(event) => update("sex", event.target.value)} maxLength={40} className="input w-full" />
              </label>
              <label className="block space-y-1 text-sm font-medium">{t("family.bloodGroup")}
                <input value={form.blood_group} onChange={(event) => update("blood_group", event.target.value)} maxLength={10} className="input w-full" />
              </label>
            </div>
            {([
              ["allergies_text", "allergies"],
              ["conditions_text", "conditions"],
              ["medicines_text", "medicines"],
            ] as const).map(([field, label]) => (
              <label key={field} className="block space-y-1 text-sm font-medium">{t(`family.${label}`)}
                <textarea value={form[field]} onChange={(event) => update(field, event.target.value)} rows={2} className="input w-full resize-y" />
              </label>
            ))}
            <button type="submit" disabled={saving || !form.name.trim()} className="btn btn-primary w-full justify-center">
              {saving ? t("stage.uploading") : t("family.save")}
            </button>
            {selected && <button type="button" onClick={() => void removeMember()} className="btn btn-ghost w-full justify-center text-crit">{t("family.remove")}</button>}
          </form>
        </section>

        {selected ? <div className="space-y-5">
          <section className="card space-y-4 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold text-ink">{t("family.documents")}</h2>
              <div className="flex gap-2">
                <Link href={`/reminders?profile_oid=${encodeURIComponent(selected.oid)}`} className="btn btn-ghost !min-h-9 !px-3 text-xs">
                  <Icon name="bell" className="h-4 w-4" />{t("family.reminders")}
                </Link>
                <label className={`btn btn-primary !min-h-9 cursor-pointer !px-3 text-xs ${uploading ? "pointer-events-none opacity-60" : ""}`}>
                  <Icon name="upload" className="h-4 w-4" />{uploading ? t("family.uploading") : t("family.uploadDocument")}
                  <input type="file" accept="image/jpeg,image/png,application/pdf" className="sr-only" disabled={uploading}
                    onChange={(event) => { void uploadDocument(event.target.files?.[0]); event.target.value = ""; }} />
                </label>
              </div>
            </div>
            {documents.length === 0 ? <p className="text-sm text-muted">{t("family.noDocuments")}</p>
              : <ul className="divide-y divide-line">{documents.map((document) => (
                <li key={document.id}>
                  <Link href={`/documents/${document.id}`} className="flex items-center justify-between gap-3 py-3 hover:text-brand">
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">{document.doc_type ? t(`docType.${document.doc_type}`) : t("docType.other")}</span>
                      <span className="block text-xs text-muted">{fmtDate(document.doc_date ?? document.created_at, i18n.language)}</span>
                    </span>
                    <span className="shrink-0 text-xs text-muted">{document.status === "processing" ? t("stage.reading") : document.status}</span>
                  </Link>
                </li>
              ))}</ul>}
          </section>
          <HealthInsightsPanel profileOid={selected.oid} />
        </div> : <section className="card flex min-h-48 items-center justify-center p-6 text-center text-sm text-muted">
          {loading ? t("auth.checking") : t("family.selectMember")}
        </section>}
      </div>
    </div>
  );
}
