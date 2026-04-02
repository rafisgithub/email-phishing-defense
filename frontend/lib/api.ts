const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  data: T;
}

async function fetchAPI<T = unknown>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Client-Type": "web",
      ...(options.headers as Record<string, string>),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.message || `API error ${res.status}`);
  }

  return res.json();
}

// ── Dashboard ────────────────────────────────────────────────────────────

export interface DashboardData {
  total_emails_scanned: number;
  total_threats: number;
  total_safe: number;
  total_suspicious: number;
  total_phishing: number;
  total_mailboxes: number;
  total_tenants: number;
  recent_detections: DetectionSummary[];
  daily_stats: { date: string; total: number; threats: number }[];
}

export const getDashboard = () =>
  fetchAPI<DashboardData>("/phishing/dashboard/");

// ── Mailboxes ────────────────────────────────────────────────────────────

export interface MailboxItem {
  id: string;
  email: string;
  display_name: string;
  is_vip: boolean;
  is_active: boolean;
  last_checked_at: string | null;
  tenant_name: string;
  message_count: number;
  threat_count: number;
  created_at: string;
}

export const getMailboxes = (search?: string) => {
  const params = search ? `?search=${encodeURIComponent(search)}` : "";
  return fetchAPI<MailboxItem[]>(`/phishing/mailboxes/${params}`);
};

// ── Detections ───────────────────────────────────────────────────────────

export interface DetectionSummary {
  id: string;
  score: number;
  verdict: "safe" | "suspicious" | "phishing";
  reason_codes: string[];
  explanations: string[];
  sender_email: string;
  sender_name: string;
  subject: string;
  mailbox_email: string;
  received_at: string;
  created_at: string;
}

export interface PaginatedDetections {
  results: DetectionSummary[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export const getDetections = (params?: Record<string, string>) => {
  const query = params ? "?" + new URLSearchParams(params).toString() : "";
  return fetchAPI<PaginatedDetections>(`/phishing/detections/${query}`);
};

export interface DetectionDetail {
  id: string;
  score: number;
  verdict: "safe" | "suspicious" | "phishing";
  reason_codes: string[];
  explanations: string[];
  evidence: Record<string, unknown>;
  rules_applied: string[];
  llm_explanation: {
    summary: string;
    reasons: string[];
    risk_level: "low" | "medium" | "high";
    user_advice: string[];
  } | null;
  message: {
    id: string;
    sender_email: string;
    sender_name: string;
    reply_to: string;
    subject: string;
    body_text: string;
    received_at: string;
    mailbox: string;
    attachments_meta: { name: string; contentType: string; size: number }[];
    headers: Record<string, string>;
  };
  links: { id: string; url: string; display_text: string; is_suspicious: boolean }[];
  actions: {
    id: string;
    action_type: string;
    status: string;
    error_message: string;
    executed_at: string | null;
    created_at: string;
  }[];
  feedbacks: { id: string; feedback_type: string; comment: string; created_at: string }[];
  created_at: string;
}

export const getDetection = (id: string) =>
  fetchAPI<DetectionDetail>(`/phishing/detections/${id}/`);

// ── Allow / Block Lists ──────────────────────────────────────────────────

export interface ListEntry {
  id: string;
  domain: string;
  reason: string;
  created_at: string;
}

export const getAllowList = () =>
  fetchAPI<ListEntry[]>("/phishing/allowlist/domain/");

export const addToAllowList = (domain: string, reason = "") =>
  fetchAPI<ListEntry>("/phishing/allowlist/domain/", {
    method: "POST",
    body: JSON.stringify({ domain, reason }),
  });

export const getBlockList = () =>
  fetchAPI<ListEntry[]>("/phishing/blocklist/domain/");

export const addToBlockList = (domain: string, reason = "") =>
  fetchAPI<ListEntry>("/phishing/blocklist/domain/", {
    method: "POST",
    body: JSON.stringify({ domain, reason }),
  });

// ── Feedback ─────────────────────────────────────────────────────────────

export const submitFeedback = (
  detectionId: string,
  feedbackType: string,
  comment = ""
) =>
  fetchAPI("/phishing/feedback/report/", {
    method: "POST",
    body: JSON.stringify({
      detection_id: detectionId,
      feedback_type: feedbackType,
      comment,
    }),
  });

// ── M365 Connection ──────────────────────────────────────────────────────

export const connectM365 = (redirectUri: string) =>
  fetchAPI<{ consent_url: string; state: string }>(
    "/phishing/connect/m365/",
    {
      method: "POST",
      body: JSON.stringify({ redirect_uri: redirectUri }),
    }
  );

export const m365Callback = (tenantId: string, adminConsent: boolean) =>
  fetchAPI("/phishing/connect/m365/callback/", {
    method: "POST",
    body: JSON.stringify({
      tenant_id: tenantId,
      admin_consent: adminConsent,
    }),
  });

// ── Auth ─────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number;
  email: string;
  role: string;
}

export const googleAuth = (accessToken: string) =>
  fetchAPI<{ user: AuthUser }>("/google-auth/", {
    method: "POST",
    body: JSON.stringify({ access_token: accessToken }),
  });
