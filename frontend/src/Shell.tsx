"use client";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiRequestError, Profile, AccountUser } from "./api";
import { ToastProvider } from "./components/Toast";
import Icon, { IconName } from "./components/Icon";
import { EmptyState, Segmented } from "./components/ui";
import { LANGS, Lang } from "./i18n";

const ProfileCtx = createContext<{ profile: Profile | null; reload: () => void }>({ profile: null, reload: () => {} });
export const useProfile = () => useContext(ProfileCtx);

const NAV: { to: string; icon: IconName; key: string }[] = [
  { to: "/health", icon: "home", key: "home" },
  { to: "/upload", icon: "upload", key: "upload" },
  { to: "/timeline", icon: "activity", key: "timeline" },
  { to: "/reminders", icon: "bell", key: "reminders" },
  { to: "/family", icon: "users", key: "family" },
  { to: "/profile", icon: "user", key: "profile" },
  { to: "/abha", icon: "shield", key: "abha" },
];

function Logo() {
  const { t } = useTranslation();
  return (
    <Link href="/" aria-label={t("home.homeLink")} className="flex min-w-0 items-center">
      <Image
        src="/curamind-logo.jpeg"
        alt={t("home.logoAlt")}
        width={520}
        height={180}
        priority
        className="h-auto w-[210px] max-w-full object-contain object-left md:w-[240px]"
      />
    </Link>
  );
}

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try { localStorage.setItem("theme-v2", dark ? "dark" : "light"); } catch { /* private mode */ }
  }, [dark]);
  return { dark, toggle: () => setDark((d) => !d) };
}

function Controls() {
  const { t, i18n } = useTranslation();
  const { dark, toggle } = useTheme();
  const change = (l: Lang) => {
    i18n.changeLanguage(l);
    try { localStorage.setItem("lang", l); } catch { /* private mode */ }
    api.setLanguage(l).catch(() => {});
  };
  return (
    <div className="flex items-center gap-2">
      <div className="scale-[0.88] origin-left"><Segmented label={t("language")} value={i18n.language as Lang} onChange={change}
        options={(Object.keys(LANGS) as Lang[]).map((k) => ({ value: k, label: k === "en" ? "EN" : LANGS[k] }))} /></div>
      <button onClick={toggle} aria-label={t("theme")} aria-pressed={dark} className="btn btn-ghost !min-h-9 !w-9 !px-0">
        <Icon name={dark ? "sun" : "moon"} className="h-4 w-4" />
      </button>
    </div>
  );
}

function Layout({ children }: { children: ReactNode }) {
  const { t, i18n } = useTranslation();
  const path = usePathname();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [down, setDown] = useState(false);
  const [account, setAccount] = useState<AccountUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);

  const reload = useCallback(() => {
    api.profile()
      .then((p) => { setProfile(p); setDown(false); })
      .catch((error) => {
        if (error instanceof ApiRequestError && (error.status === 401 || error.status === 403)) {
          setProfile(null);
          setDown(false);
          return;
        }
        setDown(true);
      });
  }, []);

  useEffect(() => {
    const publicPage = path === "/" || path === "/login" || path === "/register";
    if (publicPage) {
      setAuthChecking(false);
      return;
    }

    let cancelled = false;
    setAuthChecking(true);

    // Signed-in users use their account session. If no account session exists,
    // allow the backend's X-Visit guest profile to access the same app screens.
    api.authMe()
      .then(({ user }) => {
        if (cancelled) return;
        setAccount(user);
        return api.profile().then((p) => {
          if (!cancelled) { setProfile(p); setDown(false); }
        });
      })
      .catch(async (error) => {
        if (cancelled) return;
        setAccount(null);
        try {
          const p = await api.profile();
          if (!cancelled) { setProfile(p); setDown(false); }
        } catch (profileError) {
          if (!cancelled) {
            if (profileError instanceof ApiRequestError && (profileError.status === 401 || profileError.status === 403)) {
              setProfile(null);
              setDown(false);
              return;
            }
            setDown(true);
          }
        }
      })
      .finally(() => {
        if (!cancelled) setAuthChecking(false);
      });

    return () => { cancelled = true; };
  }, [path, router]);

  async function signOut() {
    try {
      await api.authLogout();
    } finally {
      setAccount(null);
      setProfile(null);
      router.replace("/login");
    }
  }
  const active = (n: (typeof NAV)[number]) => (n.to === "/" ? path === n.to : path.startsWith(n.to));
  const link = (on: boolean) =>
    `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition ${on ? "bg-brand-soft text-brand-strong" : "text-muted hover:bg-surface-2 hover:text-ink"}`;
  const abha = profile?.abha;
  const assistantPage = path === "/assistant";
  return (
    <div lang={i18n.language} className={`app-shell min-h-screen lang-${i18n.language.split("-")[0]} ${path === "/" ? "" : assistantPage ? "md:grid md:grid-cols-1" : "md:grid md:grid-cols-[17rem_1fr]"}`}>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-surface focus:p-3">{t("skip")}</a>

      {path !== "/" && !assistantPage && (<aside className="no-print sticky top-0 hidden h-screen flex-col gap-6 overflow-y-auto border-r border-line bg-surface/70 p-5 backdrop-blur md:flex">
        <Logo />
        <nav className="flex flex-col gap-1">
          {NAV.map((n) => <Link key={n.to} href={n.to} className={link(active(n))}><Icon name={n.icon} />{t(`nav.${n.key}`)}</Link>)}
        </nav>

        <Link href="/assistant" aria-label={t("assistant.aria")} className="block rounded-2xl border border-line bg-brand-soft p-4 transition hover:border-brand/50">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-brand-strong shadow-sm">
              <Icon name="heart" className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <p className="font-semibold text-ink">{t("assistant.name")}</p>
              <p className="text-xs font-medium text-muted">{t("assistant.tagline")}</p>
            </div>
          </div>
          <p className="mt-3 text-sm leading-5 text-ink">{t("assistant.description")}</p>
          <span className="mt-3 inline-flex rounded-full border border-line bg-white px-2.5 py-1 text-xs font-semibold text-brand-strong">
            {t("assistant.open")}
          </span>
        </Link>

        <div className="mt-auto space-y-4">
          <Link href="/abha" className="card block space-y-1 p-3.5 transition hover:border-brand/40">
            <p className="eyebrow flex items-center gap-1.5"><Icon name="shield" className="h-3.5 w-3.5" />{t("yourAbha")}</p>
            <p className={`text-sm font-semibold ${abha?.linked ? "text-ok" : "text-muted"}`}>
              {abha?.linked ? `ÃƒÂ¢Ã…â€œÃ¢â‚¬Å“ ${t("abhaLinked")}` : abha?.number || abha?.address ? t("abhaPending") : t("abhaNotLinked")}
            </p>
          </Link>
          {account && (
            <div className="space-y-2 rounded-xl border border-line p-3">
              <p className="truncate text-xs text-muted">{account.email}</p>
              <button type="button" onClick={signOut} className="btn btn-ghost w-full">
                {t("auth.signOut")}
              </button>
            </div>
          )}
          <Controls />
        </div>
      </aside>)}

      <div className={`min-w-0 ${path === "/" ? "pb-8" : "pb-28 md:pb-12"}`}>
        <header className="no-print sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-line bg-bg/85 px-4 py-3 backdrop-blur md:hidden">
          {assistantPage ? (
            <Link href="/health" aria-label={t("home.homeLink")} className="flex items-center gap-2 font-bold text-ink">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-soft text-brand-strong"><Icon name="heart" className="h-5 w-5" /></span>
              CuraMind
            </Link>
          ) : <Logo />}
          <div className="flex items-center gap-2">
            {account && (
              <button type="button" onClick={signOut} className="btn btn-ghost !min-h-9 !px-2">
                {t("auth.signOut")}
              </button>
            )}
            <Controls />
          </div>
        </header>
        <main id="main" className={`mx-auto px-4 py-6 ${assistantPage ? "max-w-7xl md:px-8 md:py-6" : "max-w-5xl md:px-10 md:py-10"}`}>
          {authChecking && path !== "/" && path !== "/login" && path !== "/register" ? <p className="py-12 text-center text-sm text-muted">{t("auth.checking")}</p> : down ? <EmptyState icon="alert" title={t("serverDown")} sub={t("serverDownSub")} /> : <ProfileCtx.Provider value={{ profile, reload }}>{children}</ProfileCtx.Provider>}
        </main>
      </div>

      {path !== "/" && !assistantPage && (<nav aria-label={t("auth.primaryNav")} className="no-print fixed inset-x-3 bottom-3 z-40 grid grid-cols-7 gap-0.5 rounded-2xl border border-line bg-surface/95 p-1 shadow-card backdrop-blur md:hidden">
        {NAV.map((n) => (
          <Link key={n.to} href={n.to}
            className={`flex min-w-0 flex-col items-center gap-0.5 rounded-lg py-2 text-[9px] font-semibold ${active(n) ? "bg-brand-soft text-brand-strong" : "text-muted"}`}>
            <Icon name={n.icon} className="h-4 w-4" /><span className="truncate">{t(`nav.${n.key}`)}</span>
          </Link>))}
      </nav>)}
    </div>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  return <ToastProvider><Layout>{children}</Layout></ToastProvider>;
}
