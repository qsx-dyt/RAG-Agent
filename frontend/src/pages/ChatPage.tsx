import { useState } from "react";
import { Button, Input, List, Layout, Modal, Popconfirm } from "antd";
import { useQuery, useMutation } from "@tanstack/react-query";
import MessageItem, { Citation } from "../components/MessageItem";
import TracePanel, { TraceStep } from "../components/TracePanel";
import {
  createConversation,
  apiFetch,
  getConversationMessages,
  renameConversation,
  deleteConversation,
} from "../api/client";
import { useChatStream, SSEEvent } from "../hooks/useChatStream";

interface ConversationItem { id: string; title: string }
interface Msg { id: string; role: "user" | "assistant"; content: string; citations: Citation[] }

export default function ChatPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [trace, setTrace] = useState<TraceStep[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [renameTarget, setRenameTarget] = useState<ConversationItem | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const { send } = useChatStream();

  const convsQuery = useQuery({ queryKey: ["conversations"],
    queryFn: () => apiFetch<ConversationItem[]>("/conversations") });

  const newConv = useMutation({
    mutationFn: createConversation,
    onSuccess: (c) => { setConversationId(c.id); setMessages([]); setTrace([]); convsQuery.refetch(); },
  });

  const delConv = useMutation({
    mutationFn: deleteConversation,
    onSuccess: (_r, id) => {
      if (conversationId === id) { setConversationId(null); setMessages([]); setTrace([]); }
      convsQuery.refetch();
    },
  });

  const renameConv = useMutation({
    mutationFn: (v: { id: string; title: string }) => renameConversation(v.id, v.title),
    onSuccess: () => { setRenameTarget(null); convsQuery.refetch(); },
  });

  const openConversation = async (c: ConversationItem) => {
    setConversationId(c.id);
    setTrace([]);
    try {
      setMessages((await getConversationMessages(c.id)) as Msg[]);
    } catch {
      setMessages([]);
    }
  };

  const onEvent = (e: SSEEvent) => {
    const data = JSON.parse(e.data);
    if (e.event === "start") {
      setConversationId(data.conversation_id);
      convsQuery.refetch();
    } else if (e.event === "agent_trace") {
      setTrace((prev) => [...prev, data]);
    } else if (e.event === "token") {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant") {
          return [...prev.slice(0, -1), { ...last, content: last.content + data.text }];
        }
        return [...prev, { id: "tmp", role: "assistant", content: data.text, citations: [] }];
      });
    } else if (e.event === "citations") {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        return [...prev.slice(0, -1), { ...last, citations: data.citations }];
      });
    } else if (e.event === "done") {
      setStreaming(false);
      convsQuery.refetch();
    }
  };

  const submit = () => {
    const text = input.trim();
    if (!text || streaming) return;
    setInput("");
    setTrace([]);
    setMessages((prev) => [...prev, { id: "u" + Date.now(), role: "user", content: text, citations: [] }]);
    setStreaming(true);
    send(text, conversationId, onEvent).catch(() => setStreaming(false));
  };

  return (
    <Layout style={{ flexDirection: "row", gap: 16 }}>
      <div style={{ width: 240 }}>
        <Button block onClick={() => newConv.mutate()} style={{ marginBottom: 8 }}>新会话</Button>
        <List
          dataSource={convsQuery.data ?? []}
          renderItem={(c) => (
            <List.Item
              style={{ cursor: "pointer", background: conversationId === c.id ? "#e6f4ff" : undefined }}
              onClick={() => openConversation(c)}
              actions={[
                <a key="rename" onClick={(e) => { e.stopPropagation(); setRenameTarget(c); setRenameTitle(c.title); }}>
                  重命名
                </a>,
                <Popconfirm key="del" title="删除该会话?" onConfirm={() => delConv.mutate(c.id)}>
                  <a onClick={(e) => e.stopPropagation()}>删除</a>
                </Popconfirm>,
              ]}
            >
              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", width: "100%" }}>
                {c.title}
              </div>
            </List.Item>
          )}
        />
      </div>
      <div style={{ flex: 1 }}>
        {messages.map((m, i) => <MessageItem key={m.id + i} role={m.role} content={m.content} citations={m.citations} />)}
        <Input.TextArea rows={3} value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="输入问题,回车发送" onPressEnter={submit} />
      </div>
      <div style={{ width: 260 }}>
        <h4>Agent 步骤</h4>
        <TracePanel trace={trace} />
      </div>
      <Modal title="重命名会话" open={!!renameTarget}
        onOk={() => { if (renameTarget && renameTitle.trim()) renameConv.mutate({ id: renameTarget.id, title: renameTitle.trim() }); }}
        onCancel={() => setRenameTarget(null)}>
        <Input value={renameTitle} onChange={(e) => setRenameTitle(e.target.value)} />
      </Modal>
    </Layout>
  );
}