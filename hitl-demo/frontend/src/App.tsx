// App.tsx
import { useState, useRef, useEffect } from "react";
import {
  sendMessage,
  resumeExecution,
  fetchState,
  type ChatResponse,
  type InterruptPayload,
} from "./api";
import { ApprovalCard } from "./ApprovalCard";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [interrupt, setInterrupt] = useState<InterruptPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, interrupt]);

  function handleResponse(res: ChatResponse) {
    setThreadId(res.thread_id);

    if (res.status === "interrupted" && res.interrupt) {
      setInterrupt(res.interrupt);
    } else {
      setInterrupt(null);
      if (res.messages) {
        setMessages(
          res.messages
            .filter((m) => m.type === "ai" || m.type === "human")
            .map((m) => ({
              role: m.type === "human" ? "user" : "assistant",
              content: m.content,
            }))
        );
      }
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const res = await sendMessage(text, threadId ?? undefined);
      handleResponse(res);
    } catch (e) {
      console.error(e);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "请求失败，请检查后端是否启动。" },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function handleApproval(decision: Record<string, unknown>) {
    if (!threadId) return;
    setLoading(true);
    setInterrupt(null);

    try {
      const res = await resumeExecution(threadId, decision);
      handleResponse(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  // 页面刷新后恢复状态
  useEffect(() => {
    const saved = localStorage.getItem("hitl_thread_id");
    if (saved) {
      fetchState(saved)
        .then((res) => {
          setThreadId(saved);
          handleResponse(res);
        })
        .catch(() => localStorage.removeItem("hitl_thread_id"));
    }
  }, []);

  useEffect(() => {
    if (threadId) localStorage.setItem("hitl_thread_id", threadId);
  }, [threadId]);

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", padding: 24 }}>
      <h2>Human-in-the-Loop 邮件审批 Demo</h2>

      <div style={{
        border: "1px solid #e5e7eb",
        borderRadius: 12,
        padding: 16,
        minHeight: 400,
        maxHeight: 600,
        overflowY: "auto",
        background: "#f9fafb",
      }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              marginBottom: 12,
            }}
          >
            <div style={{
              maxWidth: "75%",
              padding: "10px 16px",
              borderRadius: 12,
              background: msg.role === "user" ? "#3b82f6" : "#fff",
              color: msg.role === "user" ? "#fff" : "#111",
              border: msg.role === "assistant" ? "1px solid #e5e7eb" : "none",
              whiteSpace: "pre-wrap",
              fontSize: 14,
            }}>
              {msg.content}
            </div>
          </div>
        ))}

        {interrupt && (
          <ApprovalCard interrupt={interrupt} onRespond={handleApproval} />
        )}

        <div ref={bottomRef} />
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="输入消息，例如：帮我起草一封给客户的邮件"
          disabled={loading || !!interrupt}
          style={{
            flex: 1,
            padding: "10px 16px",
            borderRadius: 8,
            border: "1px solid #d1d5db",
            fontSize: 14,
          }}
        />
        <button
          onClick={handleSend}
          disabled={loading || !!interrupt}
          style={{
            padding: "10px 24px",
            borderRadius: 8,
            border: "none",
            background: "#3b82f6",
            color: "#fff",
            cursor: loading || interrupt ? "not-allowed" : "pointer",
            fontSize: 14,
          }}
        >
          发送
        </button>
      </div>
    </div>
  );
}