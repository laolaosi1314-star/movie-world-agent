// 类型安全的 API 客户端。无状态：每个请求自带 world_id + Bearer token。
// 演示模式（localStorage mwa_demo=true 或 VITE_USE_MOCK=true）自动路由到内置 mock。
import type {
  PlayerTokenOut, PlayerPortalOut, LifeArchiveOut, RomanceOut, ScandalOut, TickOut,
} from "../types";
import { getToken, getWorldId, isDemo } from "./auth";
import { mock } from "./mock";

const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
const ENV_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j?.detail || detail;
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// —— 演示模式路由 ——
function demoMode(): boolean {
  return ENV_MOCK || isDemo();
}

export const api = {
  // 玩家（身份自举）
  createPlayer(worldId: number, body: { name: string; role: string; critic_domains?: string[] }) {
    if (demoMode()) return Promise.resolve(mock.createPlayer(worldId, body));
    return request<PlayerTokenOut>(`/worlds/${worldId}/players`, {
      method: "POST", body: JSON.stringify(body),
    });
  },
  getPortal(worldId: number) {
    if (demoMode()) return Promise.resolve(mock.getPortal());
    return request<PlayerPortalOut>(`/worlds/${worldId}/players/me/portal`);
  },
  // 人生档案馆（只读聚合）
  getArchive(worldId: number, characterId: number) {
    if (demoMode()) return Promise.resolve(mock.getArchive(worldId, characterId));
    return request<LifeArchiveOut>(`/worlds/${worldId}/characters/${characterId}/archive`);
  },
  // 时间推进（任何角色皆可）
  advanceTick(worldId: number, unit = "month") {
    if (demoMode()) return Promise.resolve(mock.advanceTick(worldId, unit));
    return request<TickOut>(`/worlds/${worldId}/sim/advance`, {
      method: "POST", body: JSON.stringify({ unit }),
    });
  },
  // 人际情感网络（GM）
  listRelationships(worldId: number) {
    if (demoMode()) return Promise.resolve(mock.listRelationships());
    return request<RomanceOut[]>(`/worlds/${worldId}/relationships`);
  },
  createRomance(worldId: number, body: { character_a_id: number; character_b_id: number; romance_type?: string; is_public?: boolean; notes?: string }) {
    if (demoMode()) return Promise.resolve(mock.createRomance(worldId, body));
    return request<RomanceOut>(`/worlds/${worldId}/relationships`, {
      method: "POST", body: JSON.stringify(body),
    });
  },
  // 舆论危机（GM）
  listScandals(worldId: number) {
    if (demoMode()) return Promise.resolve(mock.listScandals());
    return request<ScandalOut[]>(`/worlds/${worldId}/scandals`);
  },
  createScandal(worldId: number, body: { character_id: number; scandal_type: string; title: string; severity?: number; exposed?: boolean; is_confirmed?: boolean }) {
    if (demoMode()) return Promise.resolve(mock.createScandal(worldId, body));
    return request<ScandalOut>(`/worlds/${worldId}/scandals`, {
      method: "POST", body: JSON.stringify(body),
    });
  },
};

export { getWorldId };
