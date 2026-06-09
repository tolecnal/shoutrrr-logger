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
  received_at: string;
  source_ip: string | null;
  custom_fields: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Plugins
// ---------------------------------------------------------------------------
export interface PluginMeta {
  id: string;        // e.g. "splunk"
  name: string;      // display name
  description: string;
  enabled: boolean;
  config: Record<string, unknown>;
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
  value: number;
  label: string;
  description: string;
  default: number;
  min_value: number;
  max_value: number;
  unit: string;
}

// Convenience typed view of all known settings
export interface AppSettings {
  retention_days: number;
  page_size: number;
  auto_refresh_interval: number;
  stats_window_days: number;
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

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
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
}

export interface AccessTokenCreated extends AccessTokenOut {
  raw_token: string;
}
