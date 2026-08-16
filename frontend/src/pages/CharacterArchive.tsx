import { useEffect, useState } from "react";
import { useAuth } from "../App";
import { api } from "../lib/api";
import { LifeArchiveOut } from "../types";
import CommercialValueMeter from "../components/CommercialValueMeter";
import LifeArchiveTimeline from "../components/LifeArchiveTimeline";
import LegacyFootnoteCard from "../components/LegacyFootnoteCard";

export default function CharacterArchive() {
  const { session } = useAuth();
  const [charId, setCharId] = useState(10);
  const [data, setData] = useState<LifeArchiveOut | null>(null);
  const [err, setErr] = useState("");

  const load = (id: number) => {
    setErr("");
    api.getArchive(session.worldId, id)
      .then(setData)
      .catch((e) => setErr(e?.detail || e?.message || "档案加载失败"));
  };

  useEffect(() => { load(charId); /* eslint-disable-next-line */ }, []);

  return (
    <>
      <div className="card">
        <div className="field" style={{ marginBottom: 0 }}>
          <label>人物 ID（演示默认 10 = 林星河）</label>
          <div className="row">
            <input type="number" value={charId} onChange={(e) => setCharId(Number(e.target.value))} />
            <button onClick={() => load(charId)}>查档案</button>
          </div>
        </div>
      </div>

      {err && <div className="card err">{err}</div>}
      {!data && !err && <div className="card muted">加载中…</div>}

      {data && (
        <>
          <div className="card">
            <div className="spread">
              <h2>{data.name}</h2>
              <span className="pill">{data.type}</span>
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
              <span className="pill">🎂 {data.birth_year ?? "—"}</span>
              <span className="pill">📈 阶段 {data.career_stage}</span>
              <span className="pill">🔥 热度 {data.heat}</span>
            </div>
            <CommercialValueMeter value={data.commercial_value} />
          </div>

          <div className="card">
            <h2>岁月沉淀 · 历史注脚</h2>
            <LegacyFootnoteCard notes={data.legacy_footnotes as Record<string, any>[]} />
          </div>

          <div className="card">
            <h2>一生时间轴</h2>
            <LifeArchiveTimeline items={data.timeline} />
          </div>

          <div className="card">
            <h2>情感关系</h2>
            {data.relationships.length === 0 && <div className="muted">无记录。</div>}
            {data.relationships.map((r: any, i) => (
              <div key={i} className="spread" style={{ padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                <span>{r.romance_type} · {r.partner_name || r.character_b_id}</span>
                <span className={`pill ${r.status === "ended" ? "tag-red" : "tag-green"}`}>{r.status}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <h2>丑闻记录</h2>
            {data.scandals.length === 0 && <div className="muted">无记录。</div>}
            {data.scandals.map((s: any, i) => (
              <div key={i} className="spread" style={{ padding: "6px 0", borderBottom: "1px solid var(--line)" }}>
                <span>{s.title}</span>
                <span className={`pill ${s.stage === "collapsed" ? "tag-red" : ""}`}>{s.stage}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
