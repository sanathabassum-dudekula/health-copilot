"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiRequestError, api, familyApi } from "@/api";

export default function AcceptFamilyInvitationPage() {
  const { t } = useTranslation();
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(true);
  const [signedIn, setSignedIn] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const invitationToken = new URLSearchParams(window.location.search).get("token") ?? "";
    setToken(invitationToken);
    window.history.replaceState({}, "", window.location.pathname);

    if (!invitationToken) {
      setError("Invitation link is missing its token.");
      setChecking(false);
      return () => { cancelled = true; };
    }

    api.authMe()
      .then(() => {
        if (!cancelled) setSignedIn(true);
      })
      .catch((authError) => {
        if (cancelled) return;
        if (!(authError instanceof ApiRequestError && authError.status === 401)) {
          setError(authError instanceof Error ? authError.message : "Could not check your sign-in.");
        }
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });

    return () => { cancelled = true; };
  }, []);

  async function acceptInvitation() {
    setError("");
    setAccepting(true);
    try {
      await familyApi.acceptInvitation(token);
      setAccepted(true);
    } catch (acceptError) {
      setError(
        acceptError instanceof Error
          ? acceptError.message
          : t("familyInvite.error")
      );
    } finally {
      setAccepting(false);
    }
  }

  const returnTo = `/family/accept?token=${encodeURIComponent(token)}`;
  const signInUrl = `/login?next=${encodeURIComponent(returnTo)}`;
  const registerUrl = `/register?next=${encodeURIComponent(returnTo)}`;

  return (
    <main className="card mx-auto mt-8 max-w-xl space-y-5 p-6">
      <div className="space-y-2">
        <p className="eyebrow">{t("familyInvite.eyebrow")}</p>
        <h1 className="text-2xl font-semibold">{t("familyInvite.title")}</h1>
        <p className="text-sm leading-6 text-muted">
          {accepted ? t("familyInvite.accepted") : t("familyInvite.description")}
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-xl border border-crit/30 bg-crit-soft px-4 py-3 text-sm text-crit">
          {error}
        </p>
      )}

      {checking ? (
        <p className="text-sm text-muted">{t("familyInvite.checking")}</p>
      ) : accepted ? (
        <Link href="/settings" className="btn btn-primary">
          {t("familyInvite.openFamilyAccess")}
        </Link>
      ) : !token ? null : signedIn ? (
        <button
          type="button"
          className="btn btn-primary"
          disabled={accepting}
          onClick={() => void acceptInvitation()}
        >
          {accepting ? t("familyInvite.accepting") : t("familyInvite.accept")}
        </button>
      ) : (
        <div className="flex flex-wrap gap-3">
          <Link href={signInUrl} className="btn btn-primary">
            {t("familyInvite.signIn")}
          </Link>
          <Link href={registerUrl} className="btn btn-ghost">
            {t("familyInvite.createAccount")}
          </Link>
        </div>
      )}
    </main>
  );
}
