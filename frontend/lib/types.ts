export type UserRole = "viewer" | "admin";

export interface UserOut {
  id: string;
  sub: string;
  email: string;
  username: string;
  full_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationOut {
  id: string;
  sender_name: string | null;
  title: string | null;
  message: string;
  severity: string;
  tags: string[];
  fingerprint: string | null;
  occurrences: number;
  state: "new" | "acknowledged" | "resolved" | string;
  received_at: string;
  last_received_at: string;
  source_ip: string | null;
  custom_fields: Record<string, unknown>;
  // Whether the current user may delete this notification (admins: always;
  // viewers: only their own non-global token's notifications).
  can_delete: boolean;
}

export interface NotificationSearchFilters {
  senders: string[];
  tags: string[];
  severities: string[];
}

// ---------------------------------------------------------------------------
// Plugins
// ---------------------------------------------------------------------------
export interface PluginProfileOut {
  id: string;
  name: string;
  enabled: boolean;
  config: Record<string, unknown>;
  rules: any[];
}

export interface PluginMeta {
  id: string;        // e.g. "splunk"
  name: string;      // display name
  description: string;
  allow_user_configs: boolean;
  profiles: PluginProfileOut[];
}

export interface UserPluginOut {
  plugin_id: string;
  name: string;
  description: string;
  profiles: PluginProfileOut[];
  /** Max profiles per plugin for this user; 0 = unlimited (admins). */
  max_profiles: number;
}

// ---------------------------------------------------------------------------
// Routing Rules
// ---------------------------------------------------------------------------
export interface RoutingRuleOut {
  id: string;
  user_id: string | null;
  name: string;
  severities: string[];
  tags: string[];
  tokens: string[];
  custom_fields: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface VersionInfo {
  version: string;
  api_version: string;
  git_hash: string;
  build_time: string;
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
export interface SettingOut {
  key: string;
  value: any;
  label: string;
  description: string;
  default: any;
  min_value: number;
  max_value: number;
  unit: string;
  value_type: "int" | "bool" | "string";
}

// Convenience typed view of all known settings
export interface AppSettings {
  retention_days: number;
  page_size: number;
  auto_refresh_interval: number;
  stats_window_days: number;
  rate_limit_per_minute: number;
  private_tokens_enabled: boolean;
  alert_states_enabled: boolean;
  user_external_delivery_enabled: boolean;
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------
export interface DayStat {
  date: string; // YYYY-MM-DD
  count: number;
}

export interface SenderStat {
  sender: string | null;
  count: number;
}

export interface NotificationStats {
  total: number;
  today: number;
  this_week: number;
  by_day: DayStat[];
  top_senders: SenderStat[];
}

// ---------------------------------------------------------------------------
// API Performance
// ---------------------------------------------------------------------------
export interface EndpointStat {
  path: string;
  method: string;
  request_count: number;
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  error_count: number;
  error_rate: number;
}

export interface RequestTimeSeries {
  time: string; // ISO datetime truncated to hour
  count: number;
  avg_ms: number;
}

export interface ApiPerformanceStats {
  total_requests: number;
  avg_ms: number;
  p95_ms: number;
  error_rate: number;
  by_endpoint: EndpointStat[];
  by_hour: RequestTimeSeries[];
  window_hours: number;
}

// Keyset/cursor-paginated response, newest first. `total`/`pages` are
// informational; navigation is driven by `next_cursor` — pass it back as the
// `cursor` query parameter to fetch the next page. `null` on the last page.
export interface CursorPage<T> {
  items: T[];
  total: number;
  page_size: number;
  pages: number;
  next_cursor: string | null;
}

export interface AccessTokenOut {
  id: string;
  user_id: string | null;
  name: string;
  expires_at: string | null;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
  is_global: boolean;
  owner_username: string | null;
  // null = inherit the global "rate_limit_per_minute" setting; 0 = unlimited
  rate_limit_override: number | null;
  // External delivery policy: whether notifications sent with this token may
  // be forwarded by plugins / emailed by alert rules.
  allow_plugin_dispatch: boolean;
  allow_email_alerts: boolean;
}

export interface AccessTokenCreated extends AccessTokenOut {
  raw_token: string;
}

// ---------------------------------------------------------------------------
// Audit Log
// ---------------------------------------------------------------------------
export interface AuditLogOut {
  id: string;
  actor_user_id: string | null;
  actor_username: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------
export interface AlertOut {
  id: string;
  user_id: string;
  notification_id: string;
  rule_id: string | null;
  is_read: boolean;
  created_at: string;
  notification?: import("./types").NotificationOut;
}

export interface AlertRuleOut {
  id: string;
  user_id: string;
  name: string;
  match_type: "exact" | "contains" | "regex";
  match_pattern: string;
  match_target: "title" | "message" | "all";
  notification_scope: "global_only" | "personal_only" | "all";
  send_email: boolean;
  created_at: string;
  updated_at: string;
}
