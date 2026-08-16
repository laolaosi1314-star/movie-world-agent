import { ReactNode } from "react";
import { useAuth } from "../App";

// 角色门控：演示模式或已持有令牌即放行。
// 后端是权威（前端渲染与否不影响权限，仅影响按钮可见性）；
// 接入真实 /me.capabilities 后可在此比对 perm / writable。
export default function RoleGate({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const allowed = session.demo || !!session.token;
  if (!allowed) return null;
  return <>{children}</>;
}
