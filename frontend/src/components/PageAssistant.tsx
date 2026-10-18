"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, AssistantConversation, AssistantMessage, familyApi, FamilyMember, Profile } from "@/api";
import { Lang } from "@/i18n";
import Icon from "./Icon";

type SpeechRecognitionEventLike = {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};
type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

const MAX_PAGE_CONTEXT = 12_000;
const SPEECH_LOCALES: Record<Lang, string> = {
  en: "en-US",
  hi: "hi-IN",
  te: "te-IN",
  ta: "ta-IN",
};

export default function PageAssistant({
  pathname,
  profile,
}: {
  pathname: string;
  profile: Profile | null;
}) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [conversation, setConversation] = useState<AssistantConversation | null>(null);
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [profileOid, setProfileOid] = useState<string>();
  const [sending, setSending] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [speakReplies, setSpeakReplies] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const voiceReplyNext = useRef(false);
  const recognizedText = useRef("");
  const languageCode = i18n.language.split("-")[0];
  const language: Lang = languageCode in SPEECH_LOCALES ? languageCode as Lang : "en";
  const voiceLanguage = profile?.voice_language && profile.voice_language in SPEECH_LOCALES
    ? profile.voice_language as Lang
    : language;

  useEffect(() => {
    const speechWindow = window as SpeechWindow;
    setVoiceSupported(Boolean(speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition));
    return () => {
      recognition.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, []);

  useEffect(() => {
    const requestedProfile = new URLSearchParams(window.location.search).get("profile_oid") || undefined;
    setProfileOid(requestedProfile);
    setConversation(null);
    setMessages([]);
    setError("");
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    familyApi.list()
      .then(({ members }) => {
        if (!cancelled) setFamilyMembers(members);
      })
      .catch(() => {
        if (!cancelled) setError(t("pageAssistant.familyUnavailable"));
      });
    return () => { cancelled = true; };
  }, [open, t]);

  useEffect(() => {
    if (!open) return;
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending, open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !sending) setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, sending]);

  function speak(text: string) {
    if (!("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    const locale = SPEECH_LOCALES[voiceLanguage];
    const voices = window.speechSynthesis.getVoices();
    utterance.lang = locale;
    utterance.voice = voices.find((voice) => voice.lang.toLowerCase() === locale.toLowerCase())
      ?? voices.find((voice) => voice.lang.split("-")[0].toLowerCase() === voiceLanguage)
      ?? null;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  function currentPageContext() {
    const page = document.getElementById("main") ?? document.querySelector("main");
    const visibleText = (page?.innerText ?? "").replace(/\n{3,}/g, "\n\n").trim();
    const context = [
      `Page: ${document.title} (${pathname})`,
      "Visible page content:",
      visibleText || t("pageAssistant.noPageText"),
    ].join("\n");
    if (context.length <= MAX_PAGE_CONTEXT) return context;
    const shortened = "\n[Page text shortened]";
    return `${context.slice(0, MAX_PAGE_CONTEXT - shortened.length)}${shortened}`;
  }

  async function sendMessage(text = draft) {
    const question = text.trim();
    if (!question || sending) return;
    setSending(true);
    setError("");
    setDraft("");

    const pendingId = -Date.now();
    const optimisticMessage: AssistantMessage = {
      id: pendingId,
      conversation_id: conversation?.id ?? 0,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimisticMessage]);

    try {
      const activeConversation = conversation
        ?? await api.createAssistantConversation(profileOid);
      if (!conversation) setConversation(activeConversation);

      const response = await api.assistantChat({
        message: question,
        language,
        voice_language: voiceLanguage,
        conversation_id: activeConversation.id,
        images: [],
        page_context: currentPageContext(),
        ...(profileOid ? { profile_oid: profileOid } : {}),
      });
      setMessages((current) => [
        ...current.filter((message) => message.id !== pendingId),
        ...response.messages,
      ]);
      if (speakReplies || voiceReplyNext.current) speak(response.spoken_answer);
      voiceReplyNext.current = false;
    } catch (requestError) {
      setMessages((current) => current.filter((message) => message.id !== pendingId));
      setDraft(question);
      setError(requestError instanceof Error ? requestError.message : t("pageAssistant.error"));
      voiceReplyNext.current = false;
    } finally {
      setSending(false);
    }
  }

  function changeProfile(nextProfileOid: string) {
    setProfileOid(nextProfileOid || undefined);
    setConversation(null);
    setMessages([]);
    setError("");
  }

  function toggleListening() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const speechWindow = window as SpeechWindow;
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setError(t("pageAssistant.voiceUnavailable"));
      return;
    }
    const instance = new Recognition();
    instance.lang = SPEECH_LOCALES[voiceLanguage];
    instance.interimResults = true;
    recognizedText.current = "";
    voiceReplyNext.current = true;
    instance.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? "")
        .join("")
        .trim();
      recognizedText.current = transcript;
      if (transcript) setDraft(transcript);
    };
    instance.onerror = () => {
      setListening(false);
      voiceReplyNext.current = false;
      setError(t("pageAssistant.voiceError"));
    };
    instance.onend = () => {
      setListening(false);
      const transcript = recognizedText.current;
      recognizedText.current = "";
      if (transcript) void sendMessage(transcript);
      else voiceReplyNext.current = false;
    };
    recognition.current = instance;
    try {
      instance.start();
      setListening(true);
      setError("");
    } catch {
      voiceReplyNext.current = false;
      setError(t("pageAssistant.voiceError"));
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage();
  }

  return (
    <div className="no-print">
      {open && (
        <section
          role="dialog"
          aria-modal="false"
          aria-label={t("pageAssistant.title")}
          className="fixed inset-x-3 bottom-24 top-4 z-50 flex flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl md:inset-x-auto md:bottom-24 md:right-6 md:top-auto md:h-[min(640px,calc(100dvh-8rem))] md:w-[min(440px,calc(100vw-3rem))]"
        >
          <header className="flex items-center gap-3 border-b border-line bg-brand-soft px-4 py-3">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-surface text-brand-strong shadow-sm">
              <Icon name="heart" className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-sm font-semibold text-ink">{t("pageAssistant.title")}</h2>
              <p className="text-xs text-muted">{t("pageAssistant.subtitle")}</p>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label={t("pageAssistant.close")}
              className="grid h-9 w-9 place-items-center rounded-xl text-muted hover:bg-surface hover:text-ink">
              <span aria-hidden="true" className="text-xl leading-none">×</span>
            </button>
          </header>

          {familyMembers.length > 0 && (
            <label className="border-b border-line px-4 py-2 text-xs text-muted">
              <span className="sr-only">{t("pageAssistant.profileScope")}</span>
              <select value={profileOid ?? ""} onChange={(event) => changeProfile(event.target.value)}
                disabled={sending} className="input w-full py-2 text-sm">
                <option value="">{t("family.myProfile")}</option>
                {familyMembers.map((member) => (
                  <option key={member.oid} value={member.oid}>{member.name}</option>
                ))}
              </select>
            </label>
          )}

          <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
            {messages.length === 0 ? (
              <div className="py-4">
                <p className="mb-4 rounded-2xl rounded-bl-md border border-line bg-surface-2 px-4 py-3 text-sm leading-6 text-ink">
                  {t("pageAssistant.greeting")}
                </p>
                <p className="mb-3 text-xs leading-5 text-muted">{t("pageAssistant.contextNotice")}</p>
                <div className="flex flex-wrap gap-2">
                  {[
                    t("pageAssistant.promptPage"),
                    t("pageAssistant.promptRecords"),
                    t("pageAssistant.promptNext"),
                  ].map((prompt) => (
                    <button key={prompt} type="button" onClick={() => void sendMessage(prompt)}
                      disabled={sending} className="rounded-full border border-line bg-surface px-3 py-2 text-left text-xs text-ink hover:border-brand hover:bg-brand-soft disabled:opacity-50">
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : messages.map((message) => (
              <article key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 text-sm leading-6 ${
                  message.role === "user"
                    ? "rounded-br-md bg-brand text-on-brand"
                    : "rounded-bl-md border border-line bg-surface-2 text-ink"
                }`}>
                  <p className="mb-1 text-[10px] font-semibold opacity-75">
                    {message.role === "user" ? t("assistant.you") : t("assistant.name")}
                  </p>
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.role === "assistant" && (
                    <button type="button" onClick={() => speak(message.content)}
                      className="mt-1 inline-flex items-center gap-1 text-xs text-muted hover:text-brand"
                      aria-label={t("assistant.readAloud")}>
                      <Icon name="volume" className="h-3.5 w-3.5" />{t("assistant.readAloud")}
                    </button>
                  )}
                </div>
              </article>
            ))}
            {sending && (
              <p role="status" className="flex items-center gap-2 text-sm text-muted">
                <Icon name="sparkles" className="h-4 w-4 animate-pulse" />{t("pageAssistant.thinking")}
              </p>
            )}
          </div>

          {error && <p role="alert" className="mx-3 mb-2 rounded-lg bg-crit-soft px-3 py-2 text-xs text-crit">{error}</p>}
          <form onSubmit={handleSubmit} className="border-t border-line bg-surface p-3">
            <label htmlFor="page-assistant-message" className="sr-only">{t("pageAssistant.inputLabel")}</label>
            <textarea id="page-assistant-message" value={draft} maxLength={2000} rows={2}
              placeholder={t("pageAssistant.placeholder")}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
              className="input min-h-12 w-full resize-none py-2.5" />
            <div className="mt-2 flex items-center gap-2">
              {voiceSupported && (
                <button type="button" onClick={toggleListening} disabled={sending}
                  aria-label={listening ? t("pageAssistant.stopListening") : t("pageAssistant.listen")}
                  aria-pressed={listening}
                  className={`btn !min-h-9 !w-9 !px-0 ${listening ? "bg-crit text-white" : "btn-ghost"}`}>
                  <Icon name="microphone" className="h-4 w-4" />
                </button>
              )}
              <button type="button" onClick={() => setSpeakReplies((value) => !value)}
                aria-pressed={speakReplies} aria-label={t("pageAssistant.speakReplies")}
                className={`btn !min-h-9 !w-9 !px-0 ${speakReplies ? "btn-soft" : "btn-ghost"}`}>
                <Icon name="volume" className="h-4 w-4" />
              </button>
              {!voiceSupported && <span className="min-w-0 flex-1 text-[11px] text-muted">{t("pageAssistant.voiceUnavailable")}</span>}
              <button type="submit" disabled={!draft.trim() || sending}
                className="btn btn-primary ml-auto !min-h-9 !px-3" aria-label={t("pageAssistant.send")}>
                <Icon name="up" className="h-4 w-4" /><span className="hidden sm:inline">{t("pageAssistant.send")}</span>
              </button>
            </div>
            <p className="mt-2 text-[10px] leading-4 text-muted">{t("pageAssistant.privacy")}</p>
          </form>
        </section>
      )}
      <button type="button" onClick={() => setOpen((value) => !value)}
        aria-expanded={open} aria-label={open ? t("pageAssistant.close") : t("pageAssistant.open")}
        className="fixed bottom-24 right-4 z-50 inline-flex min-h-12 items-center gap-2 rounded-full bg-brand px-4 text-sm font-semibold text-on-brand shadow-lg transition hover:brightness-110 md:bottom-6 md:right-6">
        <Icon name={open ? "message" : "sparkles"} className="h-5 w-5" />
        <span>{open ? t("pageAssistant.close") : t("pageAssistant.open")}</span>
      </button>
    </div>
  );
}
