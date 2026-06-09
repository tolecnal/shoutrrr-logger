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

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AccessTokenOut {
  id: string;
  user_id: string;
  name: string;
  expires_at: string | null;
  created_at: string;
  last_used_at: string | null;
  is_active: boolean;
  owner_username: string | null;
}

export interface AccessTokenCreated extends AccessTokenOut {
  raw_token: string;
}
