"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import Icon from "../../components/Icon";

const REMEMBERED_EMAIL_KEY = "curamind-remembered-email";

export default function LoginPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberEmail, setRememberEmail] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    try {
      const rememberedEmail = window.localStorage.getItem(REMEMBERED_EMAIL_KEY);
      if (rememberedEmail) {
        setEmail(rememberedEmail);
        setRememberEmail(true);
      }
    } catch {
      // Remembering an email is optional when browser storage is unavailable.
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.authLogin({ email: email.trim(), password });
      try {
        if (rememberEmail) {
          window.localStorage.setItem(REMEMBERED_EMAIL_KEY, email.trim());
        } else {
          window.localStorage.removeItem(REMEMBERED_EMAIL_KEY);
        }
      } catch {
        // Authentication should not depend on optional browser storage.
      }
      router.replace("/");
    } catch (e) {
      setError(e instanceof Error && e.message === "Incorrect email or password."
        ? t("auth.invalidCredentials")
        : t("auth.unableToSignIn"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto grid min-h-[calc(100svh-10rem)] max-w-5xl items-center gap-5 py-4 lg:grid-cols-[1.05fr_.95fr]">
      <section className="cura-gradient relative isolate flex min-h-56 flex-col justify-between overflow-hidden rounded-[1.75rem] p-6 text-white shadow-card sm:min-h-64 sm:p-9 lg:min-h-[34rem]">
        <div aria-hidden="true" className="absolute -right-16 -top-20 -z-10 h-64 w-64 rounded-full border border-white/15" />
        <div aria-hidden="true" className="absolute -bottom-24 -left-16 -z-10 h-72 w-72 rounded-full border border-white/15" />
        <div className="flex items-center gap-3">
          <span className="grid h-12 w-12 place-items-center rounded-2xl bg-white/15 text-white">
            <Icon name="heart" className="h-6 w-6" />
          </span>
          <span className="text-lg font-semibold tracking-tight">CuraMind</span>
        </div>

        <div className="relative mt-8 max-w-md space-y-3 lg:mt-0">
          <p className="text-xs font-semibold uppercase tracking-[.16em] text-white/75">{t("auth.yourHealth")}</p>
          <h2 className="text-3xl font-semibold leading-tight tracking-tight sm:text-4xl" style={{ color: "white" }}>{t("tagline")}</h2>
          <p className="max-w-sm text-sm leading-6 text-white/85">{t("auth.signInDescription")}</p>
          <div className="flex flex-wrap gap-2 pt-2">
            {[t("nav.timeline"), t("nav.profiles"), t("assistant.name")].map((feature) => (
              <span key={feature} className="rounded-full border border-white/25 bg-white/10 px-3 py-1.5 text-xs font-medium text-white">
                {feature}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className="card w-full space-y-6 p-6 sm:p-8 lg:p-9">
        <div className="space-y-2">
          <p className="eyebrow">{t("auth.welcomeBack")}</p>
          <h1 className="text-3xl font-semibold text-ink">{t("auth.signInTitle")}</h1>
          <p className="text-sm leading-6 text-muted">{t("auth.signInDescription")}</p>
        </div>

        <form onSubmit={submit} className="space-y-5">
          <label className="block space-y-1.5">
            <span className="text-sm font-medium text-ink">{t("auth.email")}</span>
            <input
              className="input w-full"
              type="email"
              autoComplete="email"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("auth.emailPlaceholder")}
            />
          </label>

          <div className="space-y-1.5">
            <label htmlFor="login-password" className="block text-sm font-medium text-ink">{t("auth.password")}</label>
            <div className="relative">
              <input
                id="login-password"
                className="input w-full pr-20"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t("auth.passwordPlaceholder")}
              />
              <button
                type="button"
                aria-label={showPassword ? t("auth.hidePassword") : t("auth.showPassword")}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((visible) => !visible)}
                className="absolute inset-y-0 right-3 my-auto rounded-md px-1 text-xs font-semibold text-brand-strong hover:underline"
              >
                {showPassword ? t("auth.hidePassword") : t("auth.showPassword")}
              </button>
            </div>
          </div>

          <label className="flex w-fit cursor-pointer items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={rememberEmail}
              onChange={(event) => {
                setRememberEmail(event.target.checked);
                if (!event.target.checked) {
                  try {
                    window.localStorage.removeItem(REMEMBERED_EMAIL_KEY);
                  } catch {
                    // The preference remains available for this page session.
                  }
                }
              }}
              className="h-4 w-4 rounded border-line accent-brand"
            />
            {t("auth.rememberEmail")}
          </label>

          {error && <p role="alert" aria-live="polite" className="text-sm text-red-600">{error}</p>}

          <button className="btn btn-primary w-full" type="submit" disabled={busy}>
            {busy ? t("auth.signingIn") : t("auth.signIn")}
          </button>
        </form>

        <div className="space-y-4 border-t border-line pt-5 text-center text-sm">
          <p className="text-muted">
            {t("auth.newToApp")}{" "}
            <Link href="/register" className="font-semibold text-brand-strong underline">
              {t("auth.createAccount")}
            </Link>
          </p>
          <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
            <Link href="/health" className="font-semibold text-brand-strong underline">{t("auth.continueAsGuest")}</Link>
            <Link href="/" className="text-muted underline">{t("auth.backHome")}</Link>
          </div>
        </div>
      </section>
    </div>
  );
}
