import { useEffect, useState } from "react";
import { useAuth } from "../App";
import { api } from "../lib/api";
import { PlayerPortalOut } from "../types";
import RoleGate from "../components/RoleGate";
import TickAdvanceFab from "../components/TickAdvanceFab";

export default function Portal() {
  const { session } = useAuth();
  const [data, setData] = useState<PlayerPortalOut | null>(null);
  const [err, setErr] = useState("");

  const reload = () => {
    api.getPortal(session.worldId)
      .then(setData)
      .catch((e) => setErr(e?.detail || e?.message || "加载失败"));
  };

  useEffect(() => {
    reload();
  }, [session.worldId]);

  if (err) return <div className="card err">{err}</div>;
  if (!data) return <div className="card muted">加载中…</div>;

  const { player, world, recent_events } = data;

  return (
    <>
      <div className="card">
        <div className="spread">
          <h2>{world.name}</h2>
          <span className="role-chip">{player.role.toUpperCase()}</span>
        </div>
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          <span className="pill">📅 {world.current_year} 年 {world.current_month} 月</span>
          <span className="pill">🎞 行业景气 {world.industry_status}</span>
          <span className="pill">⏱ 总 tick {world.total_ticks}</span>
          <span className="pill">存档状态 {world.status}</span>
        </div>
      </div>

      <div className="card">
        <h2>你的能力</h2>
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          {player.actions.map((a) => (
            <RoleGate key={a.key}>
              <span className="pill">{a.label}</span>
            </RoleGate>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>近期时间线</h2>
        {recent_events.length === 0 && <div className="muted">暂无事件。</div>}
        {recent_events.map((e) => (
          <div key={e.id} className="spread" style={{ padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{e.title}</div>
              <div className="muted">{e.category} · {e.event_date}</div>
            </div>
            {e.is_historic && <span className="pill tag-gold">历史级</span>}
          </div>
        ))}
      </div>

      <TickAdvanceFab onDone={reload} />
    </>
  );
}
