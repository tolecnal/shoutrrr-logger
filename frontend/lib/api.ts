import type {
  AccessTokenCreated,
  AccessTokenOut,
  ApiPerformanceStats,
  AppSettings,
  AuditLogOut,
  CursorPage,
  NotificationOut,
  NotificationSearchFilters,
  NotificationStats,
  PluginMeta,
  SettingOut,
  UserOut,
  VersionInfo,
} from "./types";

// Versioned base for all functional API calls
const BASE = "/api/v1";

// Unversioned base for endpoints that will never change (health, version, auth)
const BASE_UNVERSIONED = "/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    let detail: string | undefined;
    try {
      const parsed = JSON.parse(text) as { detail?: unknown };
      if (typeof parsed.detail === "string") detail = parsed.detail;
    } catch {
      // not JSON — fall through to raw text
    }
    throw new Error(detail || text || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ---- Auth ----
// /api/auth/* is intentionally unversioned. The SWR key IS the full URL
// (/api/auth/me) so we fetch it directly rather than going through apiFetch
// which would prepend BASE (/api/v1) and produce /api/v1/api/auth/me.
export const getMe = (url: string) =>
  fetch(url, { credentials: "include" }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      throw new Error(text || `HTTP ${res.status}`);
    }
    return res.json() as Promise<UserOut>;
  });

// ---- Version ----
// /api/version is intentionally unversioned — call it directly
export const fetchVersion = () =>
  fetch(`${BASE_UNVERSIONED}/version`, { credentials: "include" }).then(
    (r) => r.json() as Promise<VersionInfo>
  );

// ---- Notifications ----
export function notificationsKey(
  cursor: string | null,
  q: string,
  pageSize = 20,
  after?: string,
  before?: string,
  scope?: string,
) {
  let url = `/notifications?page_size=${pageSize}`;
  if (cursor) url += `&cursor=${encodeURIComponent(cursor)}`;
  if (q) url += `&q=${encodeURIComponent(q)}`;
  if (after) url += `&after=${encodeURIComponent(after)}`;
  if (before) url += `&before=${encodeURIComponent(before)}`;
  if (scope && scope !== "all") url += `&scope=${scope}`;
  return url;
}
// notificationsKey returns a path relative to BASE (e.g. "/notifications?...")
// so we pass it directly to apiFetch without any stripping needed.
export const fetchNotifications = (url: string) =>
  apiFetch<CursorPage<NotificationOut>>(url);

export const updateNotificationState = (id: string, state: "new" | "acknowledged" | "resolved") =>
  apiFetch<NotificationOut>(`/notifications/${id}/state`, {
    method: "PATCH",
    body: JSON.stringify({ state }),
  });

export const fetchStats = (days = 30) =>
  apiFetch<NotificationStats>(`/notifications/stats?days=${days}`);

export function exportNotificationsUrl(params: {
  q?: string;
  after?: string;
  before?: string;
  format?: "csv" | "json";
}): string {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.after) sp.set("after", params.after);
  if (params.before) sp.set("before", params.before);
  if (params.format && params.format !== "csv") sp.set("format", params.format);
  const qs = sp.toString();
  return `/api/v1/notifications/export${qs ? `?${qs}` : ""}`;
}

export const fetchSearchFilters = () =>
  apiFetch<NotificationSearchFilters>("/notifications/search-filters");

// ---- Users ----
export const fetchUsers = () => apiFetch<UserOut[]>("/admin/users");

export const createUser = (body: {
  sub: string;
  email: string;
  username: string;
  full_name?: string;
  role: "viewer" | "admin";
}) => apiFetch<UserOut>("/admin/users", { method: "POST", body: JSON.stringify(body) });

export const updateUser = (
  id: string,
  body: Partial<{ email: string; username: string; full_name: string; role: string; is_active: boolean }>
) => apiFetch<UserOut>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteUser = (id: string) =>
  apiFetch<void>(`/admin/users/${id}`, { method: "DELETE" });

// ---- Access Tokens ----
export const fetchTokens = () => apiFetch<AccessTokenOut[]>("/admin/tokens");

export const createToken = (body: {
  name: string;
  user_id?: string;
  expires_at?: string | null;
  rate_limit_override?: number | null;
}) => apiFetch<AccessTokenCreated>("/admin/tokens", { method: "POST", body: JSON.stringify(body) });

export const updateToken = (
  id: string,
  params: {
    name?: string;
    is_active?: boolean;
    rate_limit_override?: number;
    clear_rate_limit_override?: boolean;
  }
) => {
  const sp = new URLSearchParams();
  if (params.name !== undefined) sp.set("name", params.name);
  if (params.is_active !== undefined) sp.set("is_active", String(params.is_active));
  if (params.rate_limit_override !== undefined)
    sp.set("rate_limit_override", String(params.rate_limit_override));
  if (params.clear_rate_limit_override !== undefined)
    sp.set("clear_rate_limit_override", String(params.clear_rate_limit_override));
  return apiFetch<AccessTokenOut>(`/admin/tokens/${id}?${sp}`, { method: "PATCH" });
};

export const deleteToken = (id: string) =>
  apiFetch<void>(`/admin/tokens/${id}`, { method: "DELETE" });

// ---- Settings ----
export const fetchSettings = () =>
  apiFetch<SettingOut[]>("/settings");

export function settingsToMap(list: SettingOut[]): AppSettings {
  const map: Record<string, any> = {};
  for (const s of list) map[s.key] = s.value;
  return {
    retention_days: map.retention_days ?? 0,
    page_size: map.page_size ?? 20,
    auto_refresh_interval: map.auto_refresh_interval ?? 30,
    stats_window_days: map.stats_window_days ?? 30,
    rate_limit_per_minute: map.rate_limit_per_minute ?? 0,
    private_tokens_enabled: (map.private_tokens_enabled ?? 1) !== 0,
    alert_states_enabled: (map.alert_states_enabled ?? 0) !== 0,
  };
}

export const fetchAdminSettings = () =>
  apiFetch<SettingOut[]>("/admin/settings");

export const updateSettings = (values: Record<string, any>) =>
  apiFetch<SettingOut[]>("/admin/settings", {
    method: "PATCH",
    body: JSON.stringify({ values }),
  });

export const testSmtp = (values: { smtp_host: string; smtp_port: number; smtp_user: string; smtp_password: string; smtp_from_address: string }) =>
  apiFetch<void>("/admin/settings/test-smtp", {
    method: "POST",
    body: JSON.stringify(values),
  });

// ---- Personal tokens ----
export const fetchMyTokens = () => apiFetch<AccessTokenOut[]>("/me/tokens");

export const createMyToken = (body: { name: string; expires_at?: string | null }) =>
  apiFetch<AccessTokenCreated>("/me/tokens", { method: "POST", body: JSON.stringify(body) });

export const updateMyToken = (
  id: string,
  params: { name?: string; is_active?: boolean },
) => {
  const sp = new URLSearchParams();
  if (params.name !== undefined) sp.set("name", params.name);
  if (params.is_active !== undefined) sp.set("is_active", String(params.is_active));
  return apiFetch<AccessTokenOut>(`/me/tokens/${id}?${sp}`, { method: "PATCH" });
};

export const deleteMyToken = (id: string) =>
  apiFetch<void>(`/me/tokens/${id}`, { method: "DELETE" });

// ---- API Performance ----
export const fetchApiPerformance = (windowHours = 24) =>
  apiFetch<ApiPerformanceStats>(`/admin/performance?window_hours=${windowHours}`);

// ---- Plugins ----
export const fetchPlugins = () => apiFetch<PluginMeta[]>("/admin/plugins");

export const fetchCustomFieldKeys = () =>
  apiFetch<string[]>("/admin/plugins/custom-field-keys");

export const updatePlugin = (id: string, updates: { enabled?: boolean; allow_user_configs?: boolean; config?: Record<string, unknown>; rules?: any[] }) =>
  apiFetch<PluginMeta>(`/admin/plugins/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });

export const testPlugin = (id: string) =>
  apiFetch<{ detail: string }>(`/admin/plugins/${id}/test`, { method: "POST" });

// ---- User Plugins ----
export const fetchUserPlugins = () => apiFetch<import("./types").UserPluginOut[]>("/user-plugins");

export const updateUserPlugin = (id: string, updates: { enabled?: boolean; config?: Record<string, unknown>; rules?: any[] }) =>
  apiFetch<import("./types").UserPluginOut>(`/user-plugins/${id}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });

// ---- Routing Rules ----
export const fetchRoutingRules = () => apiFetch<import("./types").RoutingRuleOut[]>("/routing-rules");
export const fetchMyRoutingRules = () => apiFetch<import("./types").RoutingRuleOut[]>("/routing-rules/me");

export const createRoutingRule = (body: { name: string; severities?: string[]; tags?: string[]; tokens?: string[]; custom_fields?: Record<string, string> }) =>
  apiFetch<import("./types").RoutingRuleOut>("/routing-rules", { method: "POST", body: JSON.stringify(body) });

export const testRoutingRule = (body: { name: string; severities?: string[]; tags?: string[]; tokens?: string[]; custom_fields?: Record<string, string> }) =>
  apiFetch<import("./types").NotificationOut[]>("/routing-rules/test", { method: "POST", body: JSON.stringify(body) });

export const updateRoutingRule = (id: string, updates: { name?: string; severities?: string[]; tags?: string[]; tokens?: string[]; custom_fields?: Record<string, string> }) =>
  apiFetch<import("./types").RoutingRuleOut>(`/routing-rules/${id}`, { method: "PATCH", body: JSON.stringify(updates) });

export const deleteRoutingRule = (id: string) =>
  apiFetch<void>(`/routing-rules/${id}`, { method: "DELETE" });

export const fetchAutocompleteTags = () => apiFetch<string[]>("/routing-rules/autocomplete/tags");
export const fetchAutocompleteCustomFields = () => apiFetch<string[]>("/routing-rules/autocomplete/custom-fields");
export const fetchAutocompleteTokens = () => apiFetch<import("./types").AccessTokenOut[]>("/routing-rules/autocomplete/tokens");

// ---- Audit Log ----
export function auditLogsKey(cursor: string | null, pageSize = 20, action?: string) {
  let url = `/admin/audit-logs?page_size=${pageSize}`;
  if (cursor) url += `&cursor=${encodeURIComponent(cursor)}`;
  if (action) url += `&action=${encodeURIComponent(action)}`;
  return url;
}

export const fetchAuditLogs = (url: string) => apiFetch<CursorPage<AuditLogOut>>(url);

// ---- Alerts ----
export function alertsKey(is_read?: boolean, limit = 50, offset = 0) {
  let url = `/alerts?limit=${limit}&offset=${offset}`;
  if (is_read !== undefined) url += `&is_read=${is_read}`;
  return url;
}

export const fetchAlerts = (url: string = "/alerts?limit=50") => 
  apiFetch<import("./types").AlertOut[]>(url);

export const updateAlertState = (alert_ids: string[], is_read: boolean, all = false) => {
  let url = `/alerts/read?all=${all}`;
  alert_ids.forEach(id => url += `&alert_ids=${id}`);
  return apiFetch<void>(url, { method: "PATCH" });
};

export const deleteAlert = (id: string) =>
  apiFetch<void>(`/alerts?alert_ids=${id}`, { method: "DELETE" });

export const deleteAlerts = (alert_ids: string[], all = false) => {
  let url = `/alerts?all=${all}`;
  alert_ids.forEach(id => url += `&alert_ids=${id}`);
  return apiFetch<void>(url, { method: "DELETE" });
};

export const fetchAlertRules = () => apiFetch<import("./types").AlertRuleOut[]>("/alerts/rules");

export const createAlertRule = (body: Partial<import("./types").AlertRuleOut>) =>
  apiFetch<import("./types").AlertRuleOut>("/alerts/rules", { method: "POST", body: JSON.stringify(body) });

export const updateAlertRule = (id: string, body: Partial<import("./types").AlertRuleOut>) =>
  apiFetch<import("./types").AlertRuleOut>(`/alerts/rules/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteAlertRule = (id: string) =>
  apiFetch<void>(`/alerts/rules/${id}`, { method: "DELETE" });

export const testAlertRule = (body: Partial<import("./types").AlertRuleOut>) =>
  apiFetch<{ matched_notifications: import("./types").NotificationOut[], total_matches: number }>("/alerts/test", { method: "POST", body: JSON.stringify(body) });

export const testAlertEmail = (body: Partial<import("./types").AlertRuleOut> & { notification_id?: string }) =>
  apiFetch<void>("/alerts/test-email", { method: "POST", body: JSON.stringify(body) });

export const previewTemplate = (body: { template: string, notification_id?: string }) =>
  apiFetch<{ html: string }>("/alerts/preview-template", { method: "POST", body: JSON.stringify(body) });
