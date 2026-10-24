const BASE = "/api";  // proxied to the backend by next.config.ts

export function localDateTimeWithOffset(): string {
  const now = new Date();
  const offset = -now.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const hours = String(Math.floor(Math.abs(offset) / 60)).padStart(2, "0");
  const minutes = String(Math.abs(offset) % 60).padStart(2, "0");
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return `${local.toISOString().slice(0, -1)}${sign}${hours}:${minutes}`;
}


/**
 * Per-tab guest visitor ID.
 * Survives refreshes in the same tab but is not deliberately shared
 * between tabs. Signed-in requests are still authenticated by the
 * backend session cookie.
 */
function visitId(): string {
  // Keep guest identity across refreshes, browser tabs, and browser restarts.
  // Authenticated requests are still identified by the secure session cookie.
  const storageKey = "curamind_visit";
  const fallback = visitId as { fallbackId?: string };
  try {
    let id = localStorage.getItem(storageKey);
    if (!id || !/^[0-9a-f-]{36}$/i.test(id)) {
      id = crypto.randomUUID();
      localStorage.setItem(storageKey, id);
    }
    return id;
  } catch {
    try {
      let id = sessionStorage.getItem(storageKey);
      if (!id || !/^[0-9a-f-]{36}$/i.test(id)) {
        id = crypto.randomUUID();
        sessionStorage.setItem(storageKey, id);
      }
      return id;
    } catch {
      return fallback.fallbackId ??= crypto.randomUUID();
    }
  }
}

export class ApiRequestError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Visit", visitId());
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const r = await fetch(BASE + path, { ...init, headers });
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    const detail = payload.detail;
    const message = Array.isArray(detail)
      ? detail[0]?.msg
      : typeof detail === "object" && detail !== null
        ? detail.message
        : detail;
    throw new ApiRequestError(typeof message === "string" ? message : "Request failed", r.status);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}
const post = <T,>(p: string, body?: unknown) => req<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export type Summary = {
  headline: string; key_points: string[]; urgent_actions?: string[]; next_steps: string[];
  abnormal_explanations: { test: string; value: string; status: string; what_it_means: string; common_reasons: string; question_for_doctor: string }[];
  medicines_explained: { name: string; general_purpose: string; how_to_take: string }[];
};

export type RoutineSuggestion = {
  title: string;
  details: string;
  spoken_title: string;
  spoken_details: string;
  local_time: string;
  category: "meal" | "sleep" | "wellness";
};

export type ConfirmedPrescriptionSchedule = {
  name: string;
  strength: string | null;
  dose_pattern: string | null;
  timing: string | null;
  document_id: number;
};
export type DocumentExtraction = {
  doc_type: string;
  doc_date: string | null;
  patient_name?: string | null;
  facility?: string | null;
  practitioner?: string | null;
  admission_date?: string | null;
  discharge_date?: string | null;
  diagnoses: { name: string; source_text: string; confidence: number }[];
  medications: {
    name: string; strength?: string | null; form?: string | null;
    dose_pattern?: string | null; timing?: string | null; duration?: string | null;
    source_text: string; confidence: number;
  }[];
  lab_results: {
    test_name: string; value: string; unit?: string | null;
    ref_range?: string | null; flag_on_report?: string | null;
    source_text: string; confidence: number;
  }[];
  allergies: string[];
  impression?: string | null;
  follow_up?: string | null;
  languages_detected?: string[];
  handwritten?: boolean;
  fractures_or_injuries?: FractureInjury[];
  womens_health?: WomensHealthExtraction | null;
  needs_human_review?: boolean;
};
export type FractureInjury = {
  body_site?: string | null;
  side?: string | null;
  injury_type?: string | null;
  fracture_pattern?: string | null;
  displacement?: string | null;
  open_or_closed?: string | null;
  date_of_injury?: string | null;
  date_of_report?: string | null;
  imaging_modality?: string | null;
  reported_findings?: string | null;
  treatment_or_procedure?: string | null;
  immobilization?: string | null;
  weight_bearing_instruction?: string | null;
  follow_up_plan?: string | null;
  source_text: string;
  confidence: number;
};

export type WomensHealthExtraction = {
  pregnancy_status?: string;
  last_menstrual_period?: string | null;
  estimated_due_date?: string | null;
  gestational_age?: string | null;
  trimester?: string;
  gravida?: number | null;
  para?: number | null;
  pregnancy_complications?: string[];
  prenatal_visits_or_tests?: string[];
  delivery_date?: string | null;
  postpartum_notes?: string[];
  menstrual_history?: string | null;
  reproductive_health_notes?: string[];
  cervical_screening?: string[];
  breast_health_notes?: string[];
  menopause_or_fertility_notes?: string[];
  source_text?: string | null;
  needs_clinician_review?: boolean;
};

export type Doc = {
  id: number; doc_type: string | null; doc_date: string | null; facility: string | null; status: string; review_status: "pending" | "confirmed" | "rejected"; source: string;
  created_at?: string; practitioner?: string | null;
  summary?: Summary | null;
  extraction?: (DocumentExtraction & {
    _warnings?: string[];
    _error?: string;
    _rejected?: boolean;
  }) | null;
  observations?: Obs[]; medications?: Med[]; conditions?: { name: string }[]; allergies?: { substance: string }[];
};
export type Obs = { id: number; display_name: string; value_num: number | null; value_text: string | null; unit: string | null; ref_low: number | null; ref_high: number | null; interpretation: string | null; note: string | null };
export type Med = { id: number; brand_name: string; salt: string | null; strength: string | null; dose_pattern: string | null; timing: string | null; duration_days: number | null };
export type TimelineItem = { type: string; date: string; captured_at?: string; document_id?: number | null; title: string; detail: string | null; interpretation?: string; review_status?: "pending" | "confirmed" | "rejected"; source: string; device_name?: string | null };
export type Profile = {
  oid: string;
  name: string;
  age: number | null;
  language: string;
  voice_language: string;
  voice_reminders_enabled: boolean;
  family_reminders_enabled: boolean;
  womens_health_profile: WomensHealthProfile;
  dob: string | null;
  sex: string | null;
  blood_group: string | null;
  allergies_text: string | null;
  conditions_text: string | null;
  medicines_text: string | null;
  previous_records: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  abha: {
    number: string | null;
    address: string | null;
    linked: boolean;
  };
  conditions: string[];
  allergies: string[];
  current_medicines: {
    name: string;
    salt: string | null;
    dose_pattern: string | null;
    document_id: number;
  }[];
  latest_abnormal: {
    test: string;
    value: string | number;
    unit: string | null;
    interpretation: string;
    document_id: number;
    ref_low: number | null;
    ref_high: number | null;
  }[];
};

export type WomensHealthProfile = {
  cycle_tracker_enabled: boolean;
  pregnancy_tracker_enabled: boolean;
  menopause_fertility_enabled: boolean;
  screening_enabled: boolean;
  last_period_date: string | null;
  period_start_dates: string[];
  cycle_length_days: number | null;
  pregnancy_status: "unknown" | "pregnant" | "not_pregnant" | "postpartum";
  estimated_due_date: string | null;
  pregnancy_notes: string | null;
  menopause_notes: string | null;
  fertility_notes: string | null;
  cervical_screening_notes: string | null;
  breast_health_notes: string | null;
};

export type ProfileFields = {
  name?: string;
  dob?: string | null;
  sex?: string | null;
  age?: number | null;
  blood_group?: string | null;
  allergies_text?: string | null;
  conditions_text?: string | null;
  medicines_text?: string | null;
  previous_records?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  preferred_language?: string;
  preferred_voice_language?: "en" | "hi" | "te" | "ta";
  voice_reminders_enabled?: boolean;
  family_reminders_enabled?: boolean;
  womens_health_profile?: WomensHealthProfile;
};

export type VitalMetric = "heart_rate" | "oxygen_saturation" | "body_temperature";
export type VitalSign = {
  id: number;
  metric: VitalMetric;
  value: number;
  unit: string;
  source: "bluetooth" | "manual";
  device_name: string | null;
  captured_at: string;
};

export type AccountUser = {
  id: number;
  email: string;
  name: string;
  preferred_language: string;
};

export type AssistantMessage = {
  id: number;
  conversation_id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type AssistantConversation = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

export type AssistantImage = {
  mime_type: "image/jpeg" | "image/png" | "image/webp";
  data_base64: string;
};

export type AssistantReminderProposal = {
  title: string;
  details: string | null;
  due_at: string;
  category: "appointment" | "follow_up" | "other";
  document_id?: number;
};

export type HealthReminder = {
  id: number;
  profile_oid: string | null;
  document_id: number | null;
  title: string;
  details: string | null;
  spoken_title: string | null;
  spoken_details: string | null;
  due_at: string;
  category: "medication" | "appointment" | "follow_up" | "meal" | "sleep" | "wellness" | "other";
  recurrence: "none" | "daily" | "weekly" | "monthly";
  status: "pending" | "completed" | "dismissed";
  created_at: string;
};

export type FamilySharedReminder = HealthReminder & {
  profile_name: string;
};

export type PushSubscriptionPayload = {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
};

export type HealthInsights = {
  profile: { oid: string | null; name: string };
  flagged_results: {
    test: string;
    value: string | number | null;
    unit: string | null;
    flag: string;
    date: string | null;
    document_id: number;
  }[];
  trends: {
    test: string;
    unit: string | null;
    previous_value: number;
    latest_value: number;
    previous_date: string | null;
    latest_date: string | null;
    direction: "increased" | "decreased" | "stable";
    latest_flag: string | null;
    document_id: number;
  }[];
  follow_ups: string[];
  medicine_reminder_suggestions: {
    name: string;
    dose_pattern: string | null;
    timing: string | null;
    document_id: number;
  }[];
  wellness: { kind: "general" | "records" | "add_records" }[];
};

export const api = {
  authRegister: (body: { email: string; password: string; name: string }) =>
    post<{ user: AccountUser }>("/auth/register", body),
  authLogin: (body: { email: string; password: string }) =>
    post<{ user: AccountUser }>("/auth/login", body),
  authMe: () => req<{ user: AccountUser }>("/auth/me"),
  authLogout: () => post<{ message: string }>("/auth/logout"),
  assistantConversations: (profileOid?: string) => req<AssistantConversation[]>(`/assistant/conversations${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`),
  createAssistantConversation: (profileOid?: string) => post<AssistantConversation>(`/assistant/conversations${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`),
  deleteAssistantConversation: (id: number, profileOid?: string) => req<void>(`/assistant/conversations/${id}${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`, { method: "DELETE" }),
  assistantHistory: (conversationId?: number, profileOid?: string) => {
    const query = new URLSearchParams();
    if (conversationId) query.set("conversation_id", String(conversationId));
    if (profileOid) query.set("profile_oid", profileOid);
    const suffix = query.size ? `?${query.toString()}` : "";
    return req<AssistantMessage[]>(`/assistant/history${suffix}`);
  },
  clearAssistantHistory: (profileOid?: string) => req<void>(`/assistant/history${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`, { method: "DELETE" }),
  assistantChat: (body: {
    message: string;
    language: "en" | "hi" | "te" | "ta";
    voice_language?: "en" | "hi" | "te" | "ta";
    conversation_id: number;
    images: AssistantImage[];
    profile_oid?: string;
    page_context?: string;
    document_id?: number;
    local_now?: string;
  }) =>
    post<{
      answer: string;
      spoken_answer: string;
      voice_translation_error: boolean;
      messages: AssistantMessage[];
      reminder_proposal: AssistantReminderProposal | null;
      reminder_proposal_error: boolean;
    }>("/assistant/chat", body),
  reminders: (profileOid?: string, includeInactive = false) => {
    const query = new URLSearchParams();
    if (profileOid) query.set("profile_oid", profileOid);
    if (includeInactive) query.set("include_inactive", "true");
    return req<HealthReminder[]>(`/reminders${query.size ? `?${query}` : ""}`);
  },
  familyReminders: (profileOid?: string) =>
    req<FamilySharedReminder[]>(
      `/reminders/family${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`,
    ),
  pushConfig: (profileOid?: string) =>
    req<{ enabled: boolean; public_key: string | null }>(
      `/reminders/push/config${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`,
    ),
  savePushSubscription: (body: PushSubscriptionPayload, profileOid?: string) =>
    post<{ subscribed: boolean }>(
      `/reminders/push/subscriptions${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`,
      body,
    ),
  deletePushSubscription: (endpoint: string, profileOid?: string) =>
    req<void>(
      `/reminders/push/subscriptions${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`,
      { method: "DELETE", body: JSON.stringify({ endpoint }) },
    ),
  createReminder: (body: {
    title: string;
    details?: string;
    spoken_title?: string;
    spoken_details?: string;
    due_at: string;
    category: HealthReminder["category"];
    recurrence: HealthReminder["recurrence"];
    document_id?: number;
  }, profileOid?: string) =>
    post<HealthReminder>(`/reminders${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`, body),
  updateReminder: (id: number, body: Partial<Pick<HealthReminder, "title" | "details" | "due_at" | "category" | "recurrence" | "status">>, profileOid?: string) =>
    req<HealthReminder>(`/reminders/${id}${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`, { method: "PATCH", body: JSON.stringify(body) }),
  completeReminder: (id: number, profileOid?: string) =>
    post<HealthReminder>(`/reminders/${id}/complete${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`),
  deleteReminder: (id: number, profileOid?: string) =>
    req<void>(`/reminders/${id}${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`, { method: "DELETE" }),
  insights: (profileOid?: string) => req<HealthInsights>(`/insights${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`),
  routineSuggestions: (body: { written_language: "en" | "hi" | "te" | "ta"; voice_language: "en" | "hi" | "te" | "ta" }, profileOid?: string) =>
    post<{
      suggestions: RoutineSuggestion[];
      note: string;
      routine_basis: "confirmed_prescriptions" | "general";
      confirmed_prescription_count: number;
    }>(
      `/reminders/suggestions${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`,
      body,
    ),
  confirmedPrescriptions: (profileOid?: string) =>
    req<ConfirmedPrescriptionSchedule[]>(`/reminders/confirmed-prescriptions${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`),
  profile: () => req<Profile>("/profile"),
  vitals: (profileOid?: string) =>
    req<VitalSign[]>(`/vitals${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`),
  addVital: (
    body: Pick<VitalSign, "metric" | "value" | "source"> & {
      device_name?: string | null;
      captured_at?: string;
    },
    profileOid?: string,
  ) =>
    post<VitalSign>(
      `/vitals${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`,
      body,
    ),
  setLanguage: (preferred_language: string) => req("/profile", { method: "PUT", body: JSON.stringify({ preferred_language }) }),
  updateProfile: (body: ProfileFields) => req<Profile>("/profile", { method: "PUT", body: JSON.stringify(body) }),
  upload: (f: File, profileOid?: string) => { const fd = new FormData(); fd.append("file", f); return req<Doc>(`/documents${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`, { method: "POST", body: fd }); },
  docs: (profileOid?: string) => req<Doc[]>(`/documents${profileOid ? `?profile_oid=${encodeURIComponent(profileOid)}` : ""}`),
  doc: (id: number) => req<Doc>(`/documents/${id}`),
  reviewDocument: (
    id: number,
    decision: "confirmed" | "rejected",
    extraction?: DocumentExtraction,
  ) =>
    post<Doc>(`/documents/${id}/review`, {
      decision,
      ...(extraction ? { extraction } : {}),
    }),
  summary: (id: number, lang: string) => req<Summary>(`/documents/${id}/summary?lang=${lang}`),
  file: async (id: number) => {
    const response = await fetch(`${BASE}/documents/${id}/file`, {
      headers: { "X-Visit": visitId() },
      credentials: "same-origin",
    });
    if (!response.ok) {
      const detail = (await response.json().catch(() => ({}))).detail;
      throw new Error(typeof detail === "string" ? detail : `Could not load document (${response.status}).`);
    }
    const blob = await response.blob();
    return { url: URL.createObjectURL(blob), type: blob.type };
  },
  timeline: (types: string[]) => req<TimelineItem[]>(`/profile/timeline?types=${types.join(",")}`),
  abhaLink: (abha: string) => post<{ demo_otp: string }>("/abha/link", { abha }),
  abhaVerify: (otp: string) => post("/abha/verify", { otp }),
  abhaImport: () => post<{ imported_document_ids: number[] }>("/abha/import"),
  fhir: () => req<unknown>("/profile/fhir"),
};





export type FamilyMember = {
  oid: string;
  name: string;
  dob: string | null;
  sex: string | null;
  age: number | null;
  blood_group: string | null;
  allergies_text: string | null;
  conditions_text: string | null;
  medicines_text: string | null;
  previous_records: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  family_reminders_enabled: boolean;
  has_pin: boolean;
};

export type FamilyMemberFields = {
  name: string;
  dob?: string | null;
  sex?: string | null;
  age?: number | null;
  blood_group?: string | null;
  allergies_text?: string | null;
  conditions_text?: string | null;
  medicines_text?: string | null;
  previous_records?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
};

export type FamilyMemberCreateFields = FamilyMemberFields & {
  pin: string;
};

export type ActiveFamilyProfile = {
  type: "owner" | "family";
  active_profile: {
    oid: string;
    name: string;
    has_pin?: boolean;
  } & Partial<FamilyMember>;
};

export type FamilyInvitation = {
  id: number;
  phone_number: string;
  relationship_label: string | null;
  status: string;
  delivery_status: "not_sent" | "sending" | "sent" | "failed" | "not_configured";
  created_at: string;
  expires_at: string;
  message?: string;
};
export const familyApi = {
  list: () => req<{ members: FamilyMember[] }>("/family"),
  active: () => req<ActiveFamilyProfile>("/family/active"),
  get: (oid: string) =>
    req<FamilyMember>(`/family/${encodeURIComponent(oid)}`),
  add: (body: FamilyMemberCreateFields) =>
    post<FamilyMember>("/family", body),
  update: (oid: string, body: Partial<FamilyMemberFields>) =>
    req<FamilyMember>(`/family/${encodeURIComponent(oid)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  setPin: (oid: string, pin: string) =>
    post<{ message: string }>(`/family/${encodeURIComponent(oid)}/set-pin`, { pin }),
  unlock: (oid: string, pin: string) =>
    post<{ message: string; active_profile: FamilyMember }>(
      `/family/${encodeURIComponent(oid)}/unlock`,
      { pin },
    ),
  resetPin: (oid: string, accountPassword: string, newPin: string) =>
    post<{ message: string }>(`/family/${encodeURIComponent(oid)}/reset-pin`, {
      account_password: accountPassword,
      new_pin: newPin,
    }),
  switchToOwner: () =>
    post<{ message: string; active_profile: { oid: string; name: string } }>(
      "/family/switch-to-owner",
    ),
  invitations: () =>
    req<FamilyInvitation[]>("/family/invitations"),
  createInvitation: (body: {
    phone_number: string;
    relationship_label?: string;
  }) =>
    post<FamilyInvitation>("/family/invitations", body),
  sendInvitation: (id: number) =>
    post<FamilyInvitation>(`/family/invitations/${id}/send`),
  acceptInvitation: (token: string) =>
    post<{ ok: boolean; message: string }>("/family/invitations/accept", { token }),
  cancelInvitation: (id: number) =>
    req<{ ok: boolean; id: number; status: string }>(
      `/family/invitations/${id}`,
      { method: "DELETE" },
    ),
  remove: (oid: string) =>
    req<void>(`/family/${encodeURIComponent(oid)}`, { method: "DELETE" }),
};
