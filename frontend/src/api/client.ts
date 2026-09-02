const BASE = "/api/v1";

export function buildChatUrl(): string {
  return `${BASE}/chat`;
}

export async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const createConversation = (title = "新会话") =>
  apiFetch<{ id: string; title: string }>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });

export const getConversationMessages = (id: string) =>
  apiFetch<Array<{ id: string; role: string; content: string; citations: CitationItem[] }>>(
    `/conversations/${id}/messages`
  );

export const renameConversation = (id: string, title: string) =>
  apiFetch<{ id: string; title: string }>(`/conversations/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

export const deleteConversation = (id: string) =>
  apiFetch<{ ok: boolean }>(`/conversations/${id}`, { method: "DELETE" });

export interface CitationItem {
  index: number;
  chunk_id?: string;
  document_id?: string;
  content?: string;
  score?: number;
}

export const listDocuments = () =>
  apiFetch<Array<Record<string, unknown>>>("/documents");

export const uploadDocuments = async (files: File[]) => {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const resp = await fetch(`${BASE}/documents/upload`, { method: "POST", body: form });
  if (!resp.ok) throw new Error(`upload failed: ${resp.status}`);
  return resp.json();
};

export const deleteDocument = (id: string) =>
  apiFetch<{ ok: boolean }>(`/documents/${id}`, { method: "DELETE" });
