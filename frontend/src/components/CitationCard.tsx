export default function CitationCard({ citation }: { citation: { index: number; content?: string; score?: number } }) {
  return (
    <div style={{ border: "1px solid #d9d9d9", borderRadius: 6, padding: 8, marginBottom: 4 }}>
      <strong>[{citation.index}]</strong>{" "}
      <span style={{ color: "#666", fontSize: 12 }}>
        {citation.content?.slice(0, 120)}…
      </span>
      {typeof citation.score === "number" && (
        <span style={{ float: "right", color: "#999" }}>{citation.score.toFixed(2)}</span>
      )}
    </div>
  );
}
