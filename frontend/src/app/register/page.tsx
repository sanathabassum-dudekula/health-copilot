"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { api } from "../../api";

export default function RegisterPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (password.length < 8) {
      setError(t("auth.passwordMinError"));
      return;
    }
    if (password !== confirm) {
      setError(t("auth.passwordMismatch"));
      return;
    }

    setBusy(true);
    try {
      await api.authRegister({
        name: name.trim(),
        email: email.trim(),
        password,
      });
      router.replace("/health");
    } catch (e) {
      if (e instanceof Error && e.message === "Enter a valid email address.") {
        setError(t("auth.invalidEmail"));
      } else if (e instanceof Error && e.message.includes("already exists")) {
        setError(t("auth.emailExists"));
      } else {
        setError(t("auth.unableToCreate"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[75vh] max-w-md items-center px-4 py-10">
      <section className="card w-full space-y-6 p-6 sm:p-8">
        <div className="space-y-2">
          <p className="eyebrow">{t("auth.yourHealth")}</p>
          <h1 className="text-3xl font-semibold text-ink">{t("auth.registerTitle")}</h1>
          <p className="text-sm leading-6 text-muted">
            {t("auth.registerDescription")}
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">{t("auth.name")}</span>
            <input
              className="input w-full"
              autoComplete="name"
              required
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("auth.namePlaceholder")}
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">{t("auth.email")}</span>
            <input
              className="input w-full"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("auth.emailPlaceholder")}
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">{t("auth.password")}</span>
            <input
              className="input w-full"
              type="password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("auth.passwordMinPlaceholder")}
            />
          </label>

          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">{t("auth.confirmPassword")}</span>
            <input
              className="input w-full"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder={t("auth.confirmPasswordPlaceholder")}
            />
          </label>

          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

          <button className="btn btn-primary w-full" type="submit" disabled={busy}>
            {busy ? t("auth.creatingAccount") : t("auth.createAccount")}
          </button>
        </form>

        <p className="text-center text-sm text-muted">
          {t("auth.alreadyHaveAccount")}{" "}
          <Link href="/login" className="font-semibold text-brand-strong underline">
            {t("auth.signIn")}
          </Link>
        </p>

        <p className="text-center text-sm text-muted">
          {t("auth.preferNotRegister")}{" "}
          <Link href="/health" className="font-semibold text-brand-strong underline">
            {t("auth.continueAsGuest")}
          </Link>
        </p>
      </section>
    </div>
  );
}
