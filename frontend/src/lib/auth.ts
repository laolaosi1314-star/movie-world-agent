// 无状态鉴权：客户端是令牌（player_key）的唯一持有者，按请求携带 Bearer。
// 同时持有当前 world_id（多存档切换）与演示模式开关（mock）。
const K_TOKEN = "mwa_token";
const K_WORLD = "mwa_world";
const K_DEMO = "mwa_demo";

export function getToken(): string | null {
  return localStorage.getItem(K_TOKEN);
}
export function setToken(v: string | null) {
  if (v) localStorage.setItem(K_TOKEN, v);
  else localStorage.removeItem(K_TOKEN);
}

export function getWorldId(): number {
  return Number(localStorage.getItem(K_WORLD) || "1");
}
export function setWorldId(v: number) {
  localStorage.setItem(K_WORLD, String(v));
}

export function isDemo(): boolean {
  return localStorage.getItem(K_DEMO) === "true";
}
export function setDemo(v: boolean) {
  localStorage.setItem(K_DEMO, v ? "true" : "false");
}

export function logout() {
  setToken(null);
  setDemo(false);
}
