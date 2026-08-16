import { TimelineEntry } from "../types";

// 一生时间轴：不同 kind 用不同节点色（scandal=红 / award=金 / recovery=绿）。
export default function LifeArchiveTimeline({ items }: { items: TimelineEntry[] }) {
  if (!items?.length) return <div className="muted">暂无时间轴记录。</div>;
  return (
    <div className="timeline">
      {items.map((t, i) => (
        <div key={i} className={`tl-item ${t.kind}`}>
          <div className="tl-year">{t.year ?? "—"}</div>
          <div className="tl-title">{t.title}</div>
          <div className="tl-detail">{t.detail}</div>
        </div>
      ))}
    </div>
  );
}
