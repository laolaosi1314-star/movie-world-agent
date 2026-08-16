import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../App";
import { api } from "../lib/api";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [worldId, setWorldId] = useState(1);
  const [name, setName] = useState("掌镜人");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  // 演示模式：不连后端，直接用内置数据浏览完整 UI。
  const enterDemo = () => {
    login(null, true, worldId);
    nav("/");
  };

  const createGm = async () => {
    setBusy(true);
    setErr("");
    try {
      const res = await api.createPlayer(worldId, { name, role: "gm" });
      login(res.player_key, false, worldId);
      nav("/");
    } catch (e: any) {
      setErr(e?.detail || e?.message || "创建玩家失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      <div className="card">
        <h2>进入影视世界</h2>
        <div className="field">
          <label>世界 / 存档 ID</label>
          <input type="number" value={worldId} onChange={(e) => setWorldId(Number(e.target.value))} />
        </div>
        <div className="field">
          <label>玩家名称</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：掌镜人" />
        </div>
        <div className="muted">将以「上帝模式（GM）」身份进入，可编排情感关系与引爆丑闻。</div>
      </div>

      {err && <div className="err">{err}</div>}

      <button onClick={createGm} disabled={busy}>
        {busy ? "创建中…" : "创建 GM 玩家并进入"}
      </button>
      <button className="secondary" onClick={enterDemo}>
        免后端 · 进入演示
      </button>
      <div className="toast">
        提示：演示模式使用前端内置数据，可完整体验人生档案馆、时间轴与岁月沉淀注脚；连接真实后端请先起 uvicorn 再「创建 GM 玩家」。
      </div>
    </div>
  );
}
