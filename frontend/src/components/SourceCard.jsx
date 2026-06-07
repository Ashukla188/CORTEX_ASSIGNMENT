export default function SourceCard({ source, index }) {
  return (
    <article className="source-card">
      <div className="source-topline">
        <span className="source-index">#{index}</span>
        <span className="source-meta">
          {source.platform || "unknown"} / {source.content_type || "chunk"}
        </span>
      </div>
      <p className="source-text">{source.text || source.answer || "No text available."}</p>
      <div className="source-foot">
        <span>{source.created_at || "date unknown"}</span>
        <span>{source.score !== undefined ? `score ${Number(source.score).toFixed(3)}` : ""}</span>
      </div>
    </article>
  );
}

