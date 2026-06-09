import type {
  AccessTokenCreated,
  AccessTokenOut,
  NotificationOut,
  NotificationStats,
  PaginatedResponse,
  PluginMeta,
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
    throw new Error(text || `HTTP ${res.status}`);
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
  page: number,
  q: string,
  pageSize = 20,
  after?: string,
  before?: string
) {
  let url = `/notifications?page=${page}&page_size=${pageSize}`;
  if (q) url += `&q=${encodeURIComponent(q)}`;
  if (after) url += `&after=${encodeURIComponent(after)}`;
  if (before) url += `&before=${encodeURIComponent(before)}`;
  return url;
}
// notificationsKey returns a path relative to BASE (e.g. "/notifications?...")
// so we pass it directly to apiFetch without any stripping needed.
export const fetchNotifications = (url: string) =>
  apiFetch<PaginatedResponse<NotificationOut>>(url);

export const fetchStats = (days = 30) =>
  apiFetch<NotificationStats>(`/notifications/stats?days=${days}`);

export function exportNotificationsUrl(params: {
  q?: string;
  after?: string;
  before?: string;
}): string {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.after) sp.set("after", params.after);
  if (params.before) sp.set("before", params.before);
  const qs = sp.toString();
  return `/api/v1/notifications/export${qs ? `?${qs}` : ""}`;
}

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
  user_id: string;
  expires_at?: string | null;
}) => apiFetch<AccessTokenCreated>("/admin/tokens", { method: "POST", body: JSON.stringify(body) });

export const updateToken = (id: string, params: { name?: string; is_active?: boolean }) => {
  const sp = new URLSearchParams();
  if (params.name !== undefined) sp.set("name", params.name);
  if (params.is_active !== undefined) sp.set("is_active", String(params.is_active));
  return apiFetch<AccessTokenOut>(`/admin/tokens/${id}?${sp}`, { method: "PATCH" });
};

export const deleteToken = (id: string) =>
  apiFetch<void>(`/admin/tokens/${id}`, { method: "DELETE" });

// ---- Plugins ----
export const fetchPlugins = () => apiFetch<PluginMeta[]>("/admin/plugins");

export const fetchCustomFieldKeys = () =>
  apiFetch<string[]>("/admin/plugins/custom-field-keys");

export const updatePlugin = (id: string, body: { enabled?: boolean; config?: Record<string, unknown> }) =>
  apiFetch<PluginMeta>(`/admin/plugins/${id}`, { method: "PATCH", body: JSON.stringify(body) });

export const testPlugin = (id: string) =>
  apiFetch<{ detail: string }>(`/admin/plugins/${id}/test`, { method: "POST" });
