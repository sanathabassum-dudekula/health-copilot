"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useTranslation } from "react-i18next";
import { AssistantConversation, AssistantImage, AssistantMessage, AssistantReminderProposal as ReminderProposalData, api, familyApi, FamilyMember, localDateTimeWithOffset } from "@/api";
import Icon from "@/components/Icon";
import AssistantReminderProposal from "@/components/AssistantReminderProposal";
import { LANGS, Lang } from "@/i18n";
import { useProfile } from "@/Shell";

type PendingImage = { file: File; preview: string };
type SpeechRecognitionEventLike = {
  resultIndex: number;
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
const SPEECH_LOCALES: Record<Lang, string> = {
  en: "en-US",
  hi: "hi-IN",
  te: "te-IN",
  ta: "ta-IN",
};
const SPEAK_RESPONSES_STORAGE_KEY = "curamind_speak_replies";
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const MAX_TOTAL_IMAGE_BYTES = 8 * 1024 * 1024;

export default function AssistantPage() {
  const { t, i18n } = useTranslation();
  const { profile } = useProfile();
  const [conversations, setConversations] = useState<AssistantConversation[]>([]);
  const [familyMembers, setFamilyMembers] = useState<FamilyMember[]>([]);
  const [activeProfileOid, setActiveProfileOid] = useState<string | undefined>();
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [reminderProposal, setReminderProposal] = useState<ReminderProposalData | null>(null);
  const [proposalMessageId, setProposalMessageId] = useState<number | null>(null);
  const [reminderProposalError, setReminderProposalError] = useState(false);
  const [pendingImages, setPendingImages] = useState<PendingImage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [reportUploading, setReportUploading] = useState(false);
  const [reportId, setReportId] = useState<number | null>(null);
  const [activeDocumentId, setActiveDocumentId] = useState<number | null>(null);
  const [reportStatus, setReportStatus] = useState<"processing" | "done" | "error" | null>(null);
  const [reportError, setReportError] = useState("");
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [speakResponses, setSpeakResponses] = useState(false);
  const [voicePreferenceLoaded, setVoicePreferenceLoaded] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState("");
  const [error, setError] = useState("");
  const endOfMessages = useRef<HTMLDivElement>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const reportInput = useRef<HTMLInputElement>(null);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const imageUrls = useRef<string[]>([]);
  const historyRequest = useRef(0);
  const currentLanguage = i18n.language.split("-")[0];
  const language: Lang = currentLanguage in LANGS ? currentLanguage as Lang : "en";
  const voiceLanguage: Lang = profile && profile.voice_language in LANGS
    ? profile.voice_language as Lang
    : language;

  useEffect(() => {
    const speechWindow = window as SpeechWindow;
    setVoiceSupported(Boolean(speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition));
    return () => {
      recognition.current?.abort();
      window.speechSynthesis?.cancel();
      imageUrls.current.forEach((preview) => URL.revokeObjectURL(preview));
      imageUrls.current = [];
    };
  }, []);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("ask") === "vitals") {
      setDraft(t("assistant.promptVitals"));
    }
  }, [t]);

  useEffect(() => {
    if (voicePreferenceLoaded) return;
    try {
      setSpeakResponses(localStorage.getItem(SPEAK_RESPONSES_STORAGE_KEY) === "true");
    } catch {
      setVoiceNotice(t("assistant.voicePreferenceError"));
    } finally {
      setVoicePreferenceLoaded(true);
    }
  }, [t]);

  useEffect(() => {
    if (!voicePreferenceLoaded) return;
    try {
      localStorage.setItem(SPEAK_RESPONSES_STORAGE_KEY, String(speakResponses));
    } catch {
      setVoiceNotice(t("assistant.voicePreferenceError"));
    }
  }, [speakResponses, t, voicePreferenceLoaded]);

  useEffect(() => {
    let cancelled = false;
    async function loadChats() {
      try {
        let saved = await api.assistantConversations(activeProfileOid);
        if (saved.length === 0) {
          saved = [await api.createAssistantConversation(activeProfileOid)];
        }
        if (cancelled) return;
        setConversations(saved);
        setActiveConversationId(saved[0].id);
        const history = await api.assistantHistory(saved[0].id, activeProfileOid);
        if (!cancelled) setMessages(history);
      } catch {
        if (!cancelled) setError(t("assistant.error"));
      } finally {
        if (!cancelled) setLoadingHistory(false);
      }
    }
    void loadChats();
    return () => { cancelled = true; };
  }, [activeProfileOid]);

  useEffect(() => {
    familyApi.list()
      .then(({ members }) => {
        setFamilyMembers(members);
        const requestedProfile = new URLSearchParams(window.location.search).get("profile_oid");
        if (requestedProfile && members.some((member) => member.oid === requestedProfile)) {
          setActiveProfileOid(requestedProfile);
        }
      })
      .catch(() => setError(t("family.loadError")));
  }, [t]);

  useEffect(() => {
    endOfMessages.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending, loadingHistory]);

  function speakResponse(text: string) {
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

  async function selectConversation(conversationId: number) {
    if (conversationId === activeConversationId || sending) return;
    const requestId = ++historyRequest.current;
    setActiveConversationId(conversationId);
    setMessages([]);
    setDraft("");
    setActiveDocumentId(null);
    setReminderProposal(null);
    setProposalMessageId(null);
    setReminderProposalError(false);
    setError("");
    setLoadingHistory(true);
    pendingImages.forEach((image) => releaseImageUrl(image.preview));
    setPendingImages([]);
    try {
      const history = await api.assistantHistory(conversationId, activeProfileOid);
      if (historyRequest.current === requestId) setMessages(history);
    } catch {
      if (historyRequest.current === requestId) setError(t("assistant.error"));
    } finally {
      if (historyRequest.current === requestId) setLoadingHistory(false);
    }
  }

  async function startNewConversation() {
    if (sending) return;
    historyRequest.current += 1;
    setLoadingHistory(true);
    setError("");
    try {
      const conversation = await api.createAssistantConversation(activeProfileOid);
      setConversations((current) => [conversation, ...current]);
      setActiveConversationId(conversation.id);
      setMessages([]);
      setDraft("");
      setActiveDocumentId(null);
      setReminderProposal(null);
      setProposalMessageId(null);
      setReminderProposalError(false);
      pendingImages.forEach((image) => releaseImageUrl(image.preview));
      setPendingImages([]);
    } catch {
      setError(t("assistant.error"));
    } finally {
      setLoadingHistory(false);
    }
  }

  async function sendMessage(content = draft, documentId = activeDocumentId) {
    const message = content.trim();
    if ((!message && pendingImages.length === 0) || sending || loadingHistory || activeConversationId === null) return;

    const pendingId = -Date.now();
    const attachedImages = pendingImages;
    setMessages((current) => [...current, {
      id: pendingId,
      conversation_id: activeConversationId,
      role: "user",
      content: message || t("assistant.imageQuestion"),
      created_at: new Date().toISOString(),
    }]);
    setError("");
    setSending(true);

    try {
      const images: AssistantImage[] = await Promise.all(attachedImages.map(async ({ file }) => ({
        mime_type: file.type as AssistantImage["mime_type"],
        data_base64: await fileToBase64(file),
      })));
      const response = await api.assistantChat({
        message: message || t("assistant.imageQuestion"),
        language,
        voice_language: voiceLanguage,
        conversation_id: activeConversationId,
        images,
        local_now: localDateTimeWithOffset(),
        ...(activeProfileOid ? { profile_oid: activeProfileOid } : {}),
        ...(documentId ? { document_id: documentId } : {}),
      });
      setMessages((current) => [...current.filter((item) => item.id !== pendingId), ...response.messages]);
      const proposalMessage = response.messages[response.messages.length - 1];
      setReminderProposal(response.reminder_proposal);
      setProposalMessageId(response.reminder_proposal ? proposalMessage?.id ?? null : null);
      setReminderProposalError(response.reminder_proposal_error);
      setConversations((current) => current
        .map((conversation) => conversation.id === activeConversationId
          ? { ...conversation, title: conversation.title === "New health chat" ? message.slice(0, 120) : conversation.title, updated_at: new Date().toISOString() }
          : conversation)
        .sort((first, second) => second.updated_at.localeCompare(first.updated_at)));
      if (speakResponses) {
        if (response.voice_translation_error) {
          setVoiceNotice(t("assistant.voiceTranslationUnavailable"));
        } else {
          speakResponse(response.spoken_answer);
        }
      }
      attachedImages.forEach((item) => releaseImageUrl(item.preview));
      setPendingImages((current) => current.filter((item) => !attachedImages.includes(item)));
      setDraft("");
      if (documentId) setActiveDocumentId(documentId);
    } catch (requestError) {
      setMessages((current) => current.filter((item) => item.id !== pendingId));
      setError(requestError instanceof Error ? requestError.message : t("assistant.error"));
    } finally {
      setSending(false);
    }
  }

  async function clearHistory() {
    if (!window.confirm(t("assistant.confirmClear"))) return;
    setClearingHistory(true);
    historyRequest.current += 1;
    setError("");
    try {
      await api.clearAssistantHistory(activeProfileOid);
      setConversations([]);
      setActiveConversationId(null);
      setMessages([]);
      setActiveDocumentId(null);
      setReminderProposal(null);
      setProposalMessageId(null);
      setReminderProposalError(false);
      const conversation = await api.createAssistantConversation(activeProfileOid);
      setConversations([conversation]);
      setActiveConversationId(conversation.id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : t("assistant.error"));
    } finally {
      setClearingHistory(false);
    }
  }

  async function addImages(files: FileList | null) {
    if (!files) return;
    const accepted: PendingImage[] = [];
    let totalBytes = pendingImages.reduce((total, item) => total + item.file.size, 0);
    for (const file of Array.from(files)) {
      if (!IMAGE_TYPES.includes(file.type)) {
        setError(t("assistant.invalidImage"));
        continue;
      }
      if (file.size > MAX_IMAGE_BYTES || totalBytes + file.size > MAX_TOTAL_IMAGE_BYTES || pendingImages.length + accepted.length >= 2) {
        setError(t("assistant.imageLimit"));
        continue;
      }
      totalBytes += file.size;
      const preview = URL.createObjectURL(file);
      imageUrls.current.push(preview);
      accepted.push({ file, preview });
    }
    if (accepted.length) {
      setPendingImages((current) => [...current, ...accepted]);
      setError("");
    }
  }

  function releaseImageUrl(preview: string) {
    URL.revokeObjectURL(preview);
    imageUrls.current = imageUrls.current.filter((url) => url !== preview);
  }

  function removeImage(preview: string) {
    releaseImageUrl(preview);
    setPendingImages((current) => current.filter((item) => item.preview !== preview));
  }

  async function uploadReport(file: File | undefined) {
    if (!file) return;
    setReportUploading(true);
    setReportStatus("processing");
    setReportError("");
    setReportId(null);
    try {
      const doc = await api.upload(file, activeProfileOid);
      setReportId(doc.id);
      for (let attempt = 0; attempt < 90; attempt += 1) {
        const current = await api.doc(doc.id);
        if (current.status === "failed") {
          throw new Error(current.extraction?._error || t("assistant.reportFailed"));
        }
        if (current.status === "done") {
          setReportStatus("done");
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
      setReportError(t("assistant.reportStillProcessing"));
    } catch (requestError) {
      setReportStatus("error");
      setReportError(requestError instanceof Error ? requestError.message : t("assistant.reportFailed"));
    } finally {
      setReportUploading(false);
    }
  }

  function toggleVoiceInput() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const speechWindow = window as SpeechWindow;
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceNotice(t("assistant.voiceUnavailable"));
      return;
    }
    setVoiceNotice("");
    const instance = new Recognition();
    instance.lang = SPEECH_LOCALES[voiceLanguage];
    instance.interimResults = true;
    const draftPrefix = draft.trim();
    instance.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? "")
        .join("");
      if (transcript) setDraft(`${draftPrefix}${draftPrefix ? " " : ""}${transcript}`.trim());
    };
    instance.onerror = () => {
      setListening(false);
      setVoiceNotice(t("assistant.voiceError"));
    };
    instance.onend = () => setListening(false);
    recognition.current = instance;
    try {
      instance.start();
      setListening(true);
    } catch {
      setVoiceNotice(t("assistant.voiceError"));
      setListening(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage();
  }

  const suggestions = [
    t("assistant.promptAllergy"),
    t("assistant.promptMedicine"),
    t("assistant.promptResults"),
    t("assistant.promptVitals"),
  ];

  return (
    <div className="mx-auto max-w-7xl">
      <div className="grid items-stretch gap-4 md:min-h-[calc(100vh-8rem)] md:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="card flex min-h-28 flex-col gap-3 overflow-hidden p-3 md:sticky md:top-4 md:h-[calc(100vh-3rem)]">
          <Link href="/health" className="mb-1 hidden items-center justify-between gap-2 border-b border-line px-1 pb-3 md:flex" aria-label={t("home.homeLink")}>
            <span className="flex items-center gap-2 font-bold text-ink">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-brand-soft text-brand-strong"><Icon name="heart" className="h-5 w-5" /></span>
              CuraMind
            </span>
            <Icon name="home" className="h-4 w-4 shrink-0 text-muted" />
          </Link>
          {familyMembers.length > 0 && (
            <label className="space-y-1 text-xs font-medium text-muted">
              <span>{t("family.profileScope")}</span>
              <select value={activeProfileOid ?? ""} onChange={(event) => {
                historyRequest.current += 1;
                setActiveProfileOid(event.target.value || undefined);
                setMessages([]);
                setActiveDocumentId(null);
                setReminderProposal(null);
                setProposalMessageId(null);
                setReminderProposalError(false);
                setConversations([]);
                setActiveConversationId(null);
                setLoadingHistory(true);
              }} className="input w-full py-2 text-sm">
                <option value="">{t("family.myProfile")}</option>
                {familyMembers.map((member) => <option key={member.oid} value={member.oid}>{member.name}</option>)}
              </select>
            </label>
          )}
          <div className="flex gap-2">
            <Link href="/profiles" className="btn btn-ghost min-w-0 flex-1 justify-center !px-2 text-xs">
              <Icon name="users" className="h-4 w-4" />{t("family.title")}
            </Link>
            <Link href={`/reminders${activeProfileOid ? `?profile_oid=${encodeURIComponent(activeProfileOid)}` : ""}`} className="btn btn-ghost min-w-0 flex-1 justify-center !px-2 text-xs">
              <Icon name="bell" className="h-4 w-4" />{t("reminders.title")}
            </Link>
          </div>
          <button type="button" onClick={() => void startNewConversation()} disabled={sending || loadingHistory}
            className="btn btn-primary w-full justify-center">
            <Icon name="plus" className="h-4 w-4" />{t("assistant.newChat")}
          </button>
          <h2 className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">{t("assistant.previousChats")}</h2>
          {conversations.length === 0 ? (
            <p className="px-1 text-xs leading-5 text-muted">{t("assistant.emptyChatList")}</p>
          ) : (
            <ul className="flex gap-2 overflow-x-auto pb-1 md:min-h-0 md:flex-1 md:flex-col md:overflow-y-auto md:overflow-x-hidden">
              {conversations.map((conversation) => (
                <li key={conversation.id} className="min-w-48 md:min-w-0">
                  <button type="button" aria-pressed={activeConversationId === conversation.id}
                    onClick={() => void selectConversation(conversation.id)} disabled={sending}
                    className={`w-full rounded-xl px-3 py-2.5 text-left transition ${activeConversationId === conversation.id ? "bg-brand-soft text-brand-strong" : "text-ink hover:bg-surface-2"}`}>
                    <span className="block truncate text-sm font-medium">{conversation.title}</span>
                    <span className="mt-1 block text-[11px] text-muted">
                      {new Date(conversation.updated_at).toLocaleDateString(i18n.language)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="card flex h-[calc(100dvh-15rem)] min-h-96 min-w-0 flex-col overflow-hidden md:h-[calc(100vh-8rem)] md:min-h-[42rem]">
          <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-3 sm:px-6">
            <div>
              <p className="text-sm font-semibold text-ink">{t("assistant.title")}</p>
              <p className="mt-0.5 text-xs text-muted">{t("assistant.specialty")}</p>
            </div>
            {conversations.length > 0 && (
              <button type="button" onClick={() => void clearHistory()} disabled={sending || clearingHistory} className="btn btn-ghost !min-h-8 shrink-0 !px-2.5 text-xs">
                {t("assistant.clear")}
              </button>
            )}
          </header>
          <div className="max-h-[55vh] min-h-0 flex-1 space-y-4 overflow-y-auto p-4 sm:p-6" aria-live="polite" aria-label={t("assistant.aria")}>
            {loadingHistory ? (
              <p className="py-12 text-center text-sm text-muted" role="status">{t("assistant.loadingHistory")}</p>
            ) : messages.length === 0 ? (
              <div className="flex min-h-60 flex-col items-center justify-center text-center">
                <span className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-soft text-brand">
                  <Icon name="sparkles" className="h-7 w-7" />
                </span>
                <h2 className="mt-4 text-lg font-semibold text-ink">{t("assistant.welcome")}</h2>
                <p className="mt-2 max-w-md text-sm leading-6 text-muted">{t("assistant.disclaimer")}</p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {suggestions.map((suggestion) => (
                    <button key={suggestion} type="button" onClick={() => void sendMessage(suggestion)} disabled={sending}
                      className="rounded-full border border-line bg-surface px-3 py-2 text-left text-xs font-medium text-ink transition hover:border-brand hover:bg-brand-soft disabled:opacity-50">
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : messages.map((message) => (
              <article key={message.id} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                  message.role === "user"
                    ? "rounded-br-md bg-brand text-on-brand"
                    : "rounded-bl-md border border-line bg-surface-2 text-ink"
                }`}>
                  <p className="mb-1 text-[11px] font-semibold opacity-75">
                    {message.role === "user" ? t("assistant.you") : t("assistant.name")}
                  </p>
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.role === "assistant" && (
                    <>
                      {typeof window !== "undefined" && "speechSynthesis" in window && (
                        <button type="button" onClick={() => speakResponse(message.content)}
                          className="mt-2 inline-flex items-center gap-1.5 text-xs text-muted transition hover:text-brand"
                          aria-label={t("assistant.readAloud")} title={t("assistant.readAloud")}>
                          <Icon name="volume" className="h-3.5 w-3.5" />{t("assistant.readAloud")}
                        </button>
                      )}
                      {message.id === proposalMessageId && reminderProposal && (
                        <AssistantReminderProposal proposal={reminderProposal} profileOid={activeProfileOid} />
                      )}
                    </>
                  )}
                </div>
              </article>
            ))}
            {sending && (
              <div className="flex justify-start" role="status">
                <div className="rounded-2xl rounded-bl-md border border-line bg-surface-2 px-4 py-3 text-sm text-muted">
                  <span className="inline-flex items-center gap-2"><Icon name="sparkles" className="h-4 w-4 animate-pulse" />{t("assistant.thinking")}</span>
                </div>
              </div>
            )}
            <div ref={endOfMessages} />
          </div>

          {error && <p role="alert" className="mx-4 mb-3 rounded-xl border border-crit/30 bg-crit-soft px-3 py-2 text-sm text-crit sm:mx-6">{error}</p>}
          {reminderProposalError && <p role="status" className="mx-4 mb-3 text-xs text-high sm:mx-6">{t("assistant.reminderProposalError")}</p>}

          <form onSubmit={handleSubmit} className="shrink-0 border-t border-line bg-surface p-3 sm:p-4">
            <input ref={imageInput} type="file" accept="image/jpeg,image/png,image/webp" multiple className="sr-only"
              aria-hidden="true" tabIndex={-1}
              onChange={(event) => { void addImages(event.target.files); event.target.value = ""; }} />
            <input ref={reportInput} type="file" accept="image/jpeg,image/png,application/pdf" className="sr-only"
              aria-hidden="true" tabIndex={-1}
              onChange={(event) => { void uploadReport(event.target.files?.[0]); event.target.value = ""; }} />
            {pendingImages.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {pendingImages.map((image) => (
                  <figure key={image.preview} className="relative">
                    <img src={image.preview} alt={image.file.name} className="h-16 w-16 rounded-xl border border-line object-cover" />
                    <button type="button" onClick={() => removeImage(image.preview)} className="absolute -right-2 -top-2 grid h-6 w-6 place-items-center rounded-full bg-ink text-xs text-surface" aria-label={t("assistant.removeImage")}>×</button>
                  </figure>
                ))}
              </div>
            )}
            <label htmlFor="assistant-message" className="sr-only">{t("assistant.inputLabel")}</label>
            <textarea id="assistant-message" value={draft} onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
              maxLength={2000} rows={2} placeholder={t("assistant.placeholder")}
              className="input min-h-12 w-full resize-y py-3" />
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button type="button" className="btn btn-ghost !min-h-9 !px-3" onClick={() => imageInput.current?.click()} disabled={sending || pendingImages.length >= 2}
                aria-label={t("assistant.attachImage")} title={t("assistant.attachImage")}>
                <Icon name="image" className="h-4 w-4" /><span className="hidden sm:inline">{t("assistant.attachImage")}</span>
              </button>
              <button type="button" className="btn btn-ghost !min-h-9 !px-3" onClick={() => reportInput.current?.click()} disabled={reportUploading}
                aria-label={t("assistant.uploadReport")} title={t("assistant.uploadReport")}>
                <Icon name="file" className="h-4 w-4" /><span className="hidden sm:inline">{reportUploading ? t("assistant.reportUploading") : t("assistant.uploadReport")}</span>
              </button>
              {voiceSupported && <button type="button" disabled={sending || loadingHistory} onClick={toggleVoiceInput} aria-pressed={listening}
                className={`btn !min-h-9 !w-9 !px-0 ${listening ? "bg-crit text-white" : "btn-ghost"}`} aria-label={listening ? t("assistant.stopListening") : t("assistant.voiceInput")} title={listening ? t("assistant.stopListening") : t("assistant.voiceInput")}>
                <Icon name="microphone" className="h-4 w-4" />
              </button>}
              <button type="button" className={`btn !min-h-9 !px-3 ${speakResponses ? "btn-soft" : "btn-ghost"}`} aria-pressed={speakResponses}
                onClick={() => {
                  setSpeakResponses((current) => !current);
                  if (speakResponses) window.speechSynthesis?.cancel();
                }} disabled={typeof window === "undefined" || !("speechSynthesis" in window) || !voicePreferenceLoaded}
                title={t("assistant.speakReplies")}>
                <Icon name="volume" className="h-4 w-4" /><span className="hidden sm:inline">{t("assistant.speakReplies")}</span>
              </button>
              <button type="submit" disabled={(!draft.trim() && pendingImages.length === 0) || sending || loadingHistory}
                className="btn btn-primary ml-auto !min-h-9 !px-3" aria-label={t("assistant.send")} title={t("assistant.send")}>
                <Icon name="up" className="h-4 w-4" /><span className="hidden sm:inline">{t("assistant.send")}</span>
              </button>
            </div>
            {voiceNotice && <p role="status" className="mt-2 text-xs text-high">{voiceNotice}</p>}
            {!voiceSupported && <p className="mt-2 text-xs text-muted">{t("assistant.voiceUnavailable")}</p>}
            {reportStatus && (
              <div role={reportStatus === "error" ? "alert" : "status"} className={`mt-2 space-y-2 text-sm ${reportStatus === "error" ? "text-crit" : reportStatus === "done" ? "text-ok" : "text-muted"}`}>
                <p>{reportStatus === "processing" ? t("assistant.reportProcessing") : reportStatus === "done" ? t("assistant.reportReady") : reportError}</p>
                {reportStatus === "done" && reportId && (
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className="btn btn-soft !min-h-8 !px-3 text-xs"
                      disabled={sending || loadingHistory}
                      onClick={() => {
                        setActiveDocumentId(reportId);
                        void sendMessage(t("assistant.reportQuestion"), reportId);
                      }}>
                      {t("assistant.discussReport")}
                    </button>
                    <Link className="btn btn-ghost !min-h-8 !px-3 text-xs"
                      href={`/documents/${reportId}${activeProfileOid ? `?profile_oid=${encodeURIComponent(activeProfileOid)}` : ""}`}>
                      {t("assistant.reviewReport")}
                    </Link>
                  </div>
                )}
              </div>
            )}
            <p className="mt-2 text-xs leading-5 text-muted">{t("assistant.voiceLanguageHint")} {t("assistant.emergency")}</p>
            <p className="mt-1 text-xs leading-5 text-muted">{t("assistant.imageNote")}</p>
          </form>
        </section>
      </div>
    </div>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Could not read the selected image."));
        return;
      }
      resolve(reader.result.slice(reader.result.indexOf(",") + 1));
    };
    reader.onerror = () => reject(new Error("Could not read the selected image."));
    reader.readAsDataURL(file);
  });
}
