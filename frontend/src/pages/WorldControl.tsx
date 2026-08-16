import { useEffect, useState } from "react";
import { useAuth } from "../App";
import { api } from "../lib/api";
import { RomanceOut, ScandalOut } from "../types";
import RoleGate from "../components/RoleGate";
import TickAdvanceFab from "../components/TickAdvanceFab";

export default function WorldControl() {
  const { session } = useAuth();
  const [rels, setRels] = useState<RomanceOut[]>([]);
  const [scans, setScans] = useState<ScandalOut[]>([]);
  const [msg, setMsg] = useState("");

  const refresh = () => {
    api.listRelationships(session.worldId).then(setRels).catch(() => {});
    api.listScandals(session.worldId).then(setScans).catch(() => {});
  };
  useEffect(() => { refresh(); /* eslint-disable-next-line */ }, []);

  // —— 编排情感关系 ——
  const [aId, setAId] = useState(10);
  const [bId, setBId] = useState(11);
  const createRomance = async () => {
    try {
      await api.createRomance(session.worldId, { character_a_id: aId, character_b_id: bId, romance_type: "dating", is_public: false });
      setMsg("已编排地下恋情（随 tick 自然泄露 / 可主动官宣）");
      refresh();
    } catch (e: any) { setMsg(e?.detail || "失败"); }
  };

  // —— 引爆丑闻 ——
  const [charId, setCharId] = useState(10);
  const [title, setTitle] = useState("出轨丑闻（塌房）");
  const createScandal = async () => {
    try {
      await api.createScandal(session.worldId, {
        character_id: charId, scandal_type: "affair", title,
        severity: 9, exposed: true, is_confirmed: true,
      });
      setMsg("已引爆出轨丑闻（severity=9）→ 推 tick 至塌房，将自动拆散关系并触发商业价值归零");
      refresh();
    } catch (e: any) { setMsg(e?.detail || "失败"); }
  };

  return (
    <>
      <RoleGate>
        <div className="card">
          <h2>编排情感关系</h2>
          <div className="row">
            <input type="number" value={aId} onChange={(e) => setAId(Number(e.target.value))} placeholder="人物A" />
            <span className="muted">×</span>
            <input type="number" value={bId} onChange={(e) => setBId(Number(e.target.value))} placeholder="人物B" />
          </div>
          <button style={{ marginTop: 8 }} onClick={createRomance}>编排地下恋情</button>
          <div style={{ marginTop: 10 }}>
            {rels.map((r) => (
              <div key={r.id} className="spread" style={{ padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                <span>{r.character_a_id} × {r.character_b_id} · {r.romance_type}</span>
                <span className={`pill ${r.status === "ended" ? "tag-red" : "tag-green"}`}>{r.status}</span>
              </div>
            ))}
          </div>
        </div>
      </RoleGate>

      <RoleGate>
        <div className="card">
          <h2>引爆 / 处理丑闻</h2>
          <div className="row">
            <input type="number" value={charId} onChange={(e) => setCharId(Number(e.target.value))} placeholder="人物ID" />
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="丑闻标题" />
          </div>
          <button style={{ marginTop: 8 }} onClick={createScandal}>引爆塌房级丑闻</button>
          <div style={{ marginTop: 10 }}>
            {scans.map((s) => (
              <div key={s.id} className="spread" style={{ padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                <span>{s.title}</span>
                <span className={`pill ${s.stage === "collapsed" ? "tag-red" : ""}`}>{s.stage} · 热度{s.heat}</span>
              </div>
            ))}
          </div>
        </div>
      </RoleGate>

      {msg && <div className="toast">{msg}</div>}
      <TickAdvanceFab onDone={refresh} />
    </>
  );
}
