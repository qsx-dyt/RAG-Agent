import { marked } from "marked";
import CitationCard from "./CitationCard";

export interface Citation {
  index: number;
  chunk_id?: string;
  document_id?: string;
  content?: string;
  score?: number;
}

export default function MessageItem({ role, content, citations }: {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}) {
  if (role === "user") {
    return <div style={{ textAlign: "right" }}>{content}</div>;
  }
  const html = marked.parse(content) as string;
  return (
    <div>
      <div dangerouslySetInnerHTML={{ __html: html }} />
      {citations && citations.length > 0 && (
        <div style={{ marginTop: 8 }}>
          {citations.map((c) => <CitationCard key={c.index} citation={c} />)}
        </div>
      )}
    </div>
  );
}
