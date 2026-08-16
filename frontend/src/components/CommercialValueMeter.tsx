// 商业价值断崖条：直观呈现「塌房 → 价值归零」的冲击。
export default function CommercialValueMeter({ value }: { value?: number | null }) {
  const v = value ?? 0;
  const pct = Math.max(0, Math.min(100, v));
  return (
    <div>
      <div className="spread">
        <span className="muted">商业价值指数</span>
        <b style={{ color: pct < 30 ? "var(--red)" : "var(--ink)" }}>{v.toFixed(1)}</b>
      </div>
      <div className="meter" style={{ marginTop: 6 }}>
        <i style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
