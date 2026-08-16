// 与后端 API_CONTRACT.md / 各 schemas 对齐的前端类型。
// 这是前端唯一需要"对齐后端"的地方；后端字段变更时同步此处即可。

export type PlayerRole = "audience" | "critic" | "investor" | "gm";

export type RomanceType = "dating" | "rumor" | "married" | "cohabit";
export type RomanceStatus = "active" | "ended";
export type AdvanceUnit = "month" | "quarter" | "halfyear" | "year";

export interface PlayerCapability {
  key: string;
  label: string;
  permission: string;
  requires_world_writable: boolean;
}

export interface PlayerOut {
  id: number;
  world_id: number;
  name: string;
  role: PlayerRole;
  critic_domains?: string[] | null;
  bio?: string | null;
  is_active: boolean;
  created_at?: string | null;
}

export interface PlayerMeOut extends PlayerOut {
  capabilities: string[];
  actions: PlayerCapability[];
}

export interface PlayerTokenOut {
  player: PlayerOut;
  player_key: string;
}

export interface WorldSnapshot {
  id: number;
  name: string;
  current_year: number;
  current_month: number;
  industry_status: string;
  status: string;
  total_ticks: number;
}

export interface EventOut {
  id: number;
  world_id: number;
  tick_id?: number | null;
  event_date: string;
  level: string;
  category?: string | null;
  title: string;
  description?: string | null;
  causal_chain?: Record<string, unknown> | null;
  affected_entities?: Record<string, unknown> | null;
  is_historic: boolean;
}

export interface PlayerPortalOut {
  player: PlayerMeOut;
  world: WorldSnapshot;
  recent_events: EventOut[];
}

export interface RomanceOut {
  id: number;
  world_id: number;
  character_a_id: number;
  character_b_id: number;
  romance_type: RomanceType;
  status: RomanceStatus;
  is_public: boolean;
  publicness: number;
  reacted_tick?: number | null;
  child_count: number;
  started_tick: number;
  ended_tick?: number | null;
  ended_reason?: string | null;
  created_by?: string | null;
  notes?: string | null;
  created_at?: string | null;
}

export interface TimelineEntry {
  year?: number | null;
  kind: string;
  title: string;
  detail: string;
  significance: number;
}

export interface LifeArchiveOut {
  character_id: number;
  name: string;
  type: string;
  birth_year?: number | null;
  career_stage: string;
  status: string;
  heat: number;
  commercial_value?: number | null;
  award_summary: Record<string, unknown>;
  awards: Record<string, unknown>[];
  commercial: Record<string, unknown>[];
  scandals: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
  career_history: Record<string, unknown>[];
  major_events: Record<string, unknown>[];
  timeline: TimelineEntry[];
  legacy_footnotes: Record<string, unknown>[];
}

export interface ScandalOut {
  id: number;
  world_id: number;
  character_id: number;
  related_project_id?: number | null;
  scandal_type: string;
  title: string;
  severity: number;
  evidence_strength: number;
  is_confirmed: boolean;
  stage: string;
  heat: number;
  public_opinion: number;
  exposed_tick?: number | null;
  erupted_tick?: number | null;
  resolved_tick?: number | null;
  created_by?: string | null;
  notes?: string | null;
  created_at?: string | null;
}

export interface TickOut {
  id: number;
  world_id: number;
  tick_index: number;
  unit: string;
  from_date: string;
  to_date: string;
  summary?: string | null;
}
