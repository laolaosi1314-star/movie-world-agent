// 内置演示数据：无需后端即可浏览完整 UI（演示模式 / 离线预览）。
// 数据与真实后端契约同构；本模块仅用于"先看界面"。
import type {
  PlayerTokenOut,
  PlayerPortalOut,
  LifeArchiveOut,
  RomanceOut,
  ScandalOut,
  TickOut,
} from "../types";

const WORLD = {
  id: 1,
  name: "璀璨星河",
  current_year: 2026,
  current_month: 1,
  industry_status: "boom",
  status: "active",
  total_ticks: 24,
};

const GM_PLAYER = {
  id: 1,
  world_id: 1,
  name: "掌镜人（GM）",
  role: "gm" as const,
  critic_domains: null,
  bio: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
};

// 演示用档案：一位"偶像歌手"从爆红到塌房再洗白的一生，
// 用于展示人生档案馆的时间轴与岁月沉淀注脚。
const ARCHIVE_10: LifeArchiveOut = {
  character_id: 10,
  name: "林星河",
  type: "singer",
  birth_year: 1998,
  career_stage: "decline",
  status: "active",
  heat: 38,
  commercial_value: 13.4,
  award_summary: { wins: 7, nominations: 15, historic: 1 },
  awards: [
    { award_name: "金唱片奖", category: "最佳男歌手", result: "win", year: 2020 },
    { award_name: "亚洲音乐盛典", category: "年度艺人", result: "win", year: 2022 },
  ],
  commercial: [
    { brand_name: "Aurelia 高奢", tier: "luxury", annual_fee: 1200, status: "breached" },
    { brand_name: "霓虹运动", tier: "mass", annual_fee: 300, status: "terminated" },
  ],
  scandals: [
    { title: "深夜密会绯闻", scandal_type: "affair", stage: "resolved", severity: 4 },
    { title: "出轨丑闻（塌房）", scandal_type: "affair", stage: "collapsed", severity: 9, is_confirmed: true },
  ],
  relationships: [
    { romance_type: "dating", partner_name: "苏晚（演员）", status: "ended", reason: "因出轨传闻拆散" },
  ],
  career_history: [{ project: "《星轨》", role: "男主", year: 2021, result: "爆款" }],
  major_events: [{ title: "金唱片封王", year: 2020 }, { title: "塌房之夜", year: 2024 }],
  timeline: [
    { year: 2018, kind: "debut", title: "选秀出道", detail: "以偶像身份出道，粉丝狂热。", significance: 2 },
    { year: 2020, kind: "award", title: "金唱片最佳男歌手", detail: "事业第一座重量级奖杯。", significance: 3 },
    { year: 2022, kind: "romance", title: "与演员苏晚恋情曝光", detail: "地下恋情被拍，粉丝两极分化。", significance: 3 },
    { year: 2024, kind: "scandal", title: "塌房之夜：出轨丑闻坐实", detail: "商业价值断崖式归零，高奢解约赔付违约金。", significance: 5 },
    { year: 2025, kind: "recovery", title: "低调复出", detail: "以独立音乐人身份缓慢重建口碑。", significance: 2 },
  ],
  legacy_footnotes: [
    { tone: "warn", text: "「塌房之夜」后，长期记忆标记 char:10:notorious —— 此后所有正面曝光都带一层公众质疑底色。" },
    { tone: "info", text: "商业价值经 §17.1 违约金重挫后长期低位（约 13%），印证「真金白银的代价」。", value: 13.4 },
    { tone: "honor", text: "早年金唱片封王仍被记入 char:10:honor，作为洗白期的信用锚点。", value: 7 },
  ],
};

let relSeq = 100;
let scanSeq = 200;
const romances: RomanceOut[] = [
  {
    id: 101, world_id: 1, character_a_id: 10, character_b_id: 11,
    romance_type: "dating", status: "ended", is_public: true, publicness: 100,
    reacted_tick: 22, child_count: 0, started_tick: 18, ended_tick: 26,
    ended_reason: "因出轨传闻拆散", created_by: "1", notes: null, created_at: null,
  },
];
const scandals: ScandalOut[] = [
  {
    id: 201, world_id: 1, character_id: 10, related_project_id: null,
    scandal_type: "affair", title: "出轨丑闻（塌房）", severity: 9, evidence_strength: 8,
    is_confirmed: true, stage: "collapsed", heat: 96, public_opinion: 12,
    exposed_tick: 24, erupted_tick: 25, resolved_tick: null, created_by: "1",
    notes: null, created_at: "2024-06-01T00:00:00Z",
  },
];

function portal(): PlayerPortalOut {
  return {
    player: {
      ...GM_PLAYER,
      capabilities: ["world:read", "sim:advance", "entity:create", "world:intervene"],
      actions: [
        { key: "sim:advance", label: "推进时间", permission: "sim:advance", requires_world_writable: false },
        { key: "relationship:manage", label: "编排情感关系", permission: "relationship:manage", requires_world_writable: true },
        { key: "crisis:manage", label: "引爆/处理丑闻", permission: "crisis:manage", requires_world_writable: true },
      ],
    },
    world: { ...WORLD },
    recent_events: [
      { id: 1, world_id: 1, event_date: "2024-06-01", level: "major", category: "情感争议", title: "林星河出轨丑闻塌房", description: "商业价值归零，高奢解约。", is_historic: true },
      { id: 2, world_id: 1, event_date: "2024-05-20", level: "important", category: "商业", title: "Aurelia 高奢宣布解约", description: "触发道德条款违约金。", is_historic: false },
    ],
  };
}

export const mock = {
  createPlayer(_worldId: number, _body: unknown): PlayerTokenOut {
    return { player: { ...GM_PLAYER }, player_key: "demo_gm_key_0000000000" };
  },
  getPortal(): PlayerPortalOut {
    return portal();
  },
  getArchive(_worldId: number, charId: number): LifeArchiveOut {
    if (charId === 10) return ARCHIVE_10;
    return { ...ARCHIVE_10, character_id: charId, name: `角色 #${charId}`, commercial_value: 50, heat: 60, legacy_footnotes: [] };
  },
  advanceTick(_worldId: number, _unit: string): TickOut {
    WORLD.current_month += 1;
    if (WORLD.current_month > 12) { WORLD.current_month = 1; WORLD.current_year += 1; }
    WORLD.total_ticks += 1;
    return {
      id: WORLD.total_ticks, world_id: 1, tick_index: WORLD.total_ticks, unit: _unit,
      from_date: "2026-01-01T00:00:00Z", to_date: "2026-02-01T00:00:00Z", summary: "演示推进一个时间单位。",
    };
  },
  listRelationships(): RomanceOut[] {
    return romances;
  },
  createRomance(_worldId: number, body: any): RomanceOut {
    const r: RomanceOut = {
      id: ++relSeq, world_id: 1, character_a_id: body.character_a_id,
      character_b_id: body.character_b_id, romance_type: body.romance_type || "dating",
      status: "active", is_public: !!body.is_public, publicness: body.publicness || 0,
      reacted_tick: null, child_count: 0, started_tick: WORLD.total_ticks,
      created_by: "1", notes: body.notes || null, created_at: null,
    };
    romances.push(r);
    return r;
  },
  createScandal(_worldId: number, body: any): ScandalOut {
    const s: ScandalOut = {
      id: ++scanSeq, world_id: 1, character_id: body.character_id,
      related_project_id: body.related_project_id ?? null, scandal_type: body.scandal_type || "other",
      title: body.title, severity: body.severity ?? 5, evidence_strength: body.evidence_strength ?? 5,
      is_confirmed: !!body.is_confirmed, stage: body.exposed === false ? "latent" : "spreading",
      heat: 60, public_opinion: 50, exposed_tick: WORLD.total_ticks,
      erupted_tick: null, resolved_tick: null, created_by: "1", notes: body.notes || null,
      created_at: new Date().toISOString(),
    };
    scandals.push(s);
    return s;
  },
  listScandals(): ScandalOut[] {
    return scandals;
  },
};
