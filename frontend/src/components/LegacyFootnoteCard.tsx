// 岁月沉淀注脚：读取长期记忆（char:{id}:notorious / commercial / honor），
// 随岁月沉淀「动态渲染」——例如塌房后所有正面曝光都带一层公众质疑底色。
export default function LegacyFootnoteCard({ notes }: { notes: Record<string, any>[] }) {
  if (!notes?.length) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {notes.map((n, i) => (
        <div key={i} className={`footnote ${n.tone || "info"}`}>
          {n.text}
          {typeof n.value === "number" && <b style={{ marginLeft: 6 }}>({n.value})</b>}
        </div>
      ))}
    </div>
  );
}
