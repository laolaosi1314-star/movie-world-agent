import { useState } from "react";
import { useAuth } from "../App";
import { api } from "../lib/api";

// 浮动「推进时间」按钮：任何角色皆可推进 tick。
export default function TickAdvanceFab({ onDone }: { onDone?: () => void }) {
  const { session } = useAuth();
  const [busy, setBusy] = useState(false);
  const advance = async () => {
    setBusy(true);
    try {
      await api.advanceTick(session.worldId, "month");
      onDone?.();
    } catch (e: any) {
      alert(e?.detail || e?.message || "推进失败");
    } finally {
      setBusy(false);
    }
  };
  return (
    <button className="fab" onClick={advance} disabled={busy} title="推进一个时间单位">
      {busy ? "…" : "推进"}
    </button>
  );
}
