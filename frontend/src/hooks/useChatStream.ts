import { buildChatUrl } from "../api/client";

export interface SSEEvent {
  event: string;
  data: string;
}

export function parseSSE(raw: string, onEvent: (e: SSEEvent) => void): void {
  for (const block of raw.split("\n\n")) {
    if (!block.trim()) continue;
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) event = line.slice(7);
      else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
    }
    if (dataLines.length) onEvent({ event, data: dataLines.join("\n") });
  }
}

export function useChatStream() {
  const send = async (
    message: string,
    conversationId: string | null,
    onEvent: (e: SSEEvent) => void
  ) => {
    const resp = await fetch(buildChatUrl(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message }),
    });
    if (!resp.body) throw new Error("no response body");
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const idx = buffer.lastIndexOf("\n\n");
      if (idx >= 0) {
        parseSSE(buffer.slice(0, idx), onEvent);
        buffer = buffer.slice(idx + 2);
      }
    }
    if (buffer.trim()) parseSSE(buffer, onEvent);
  };
  return { send };
}
