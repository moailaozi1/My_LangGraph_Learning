// api.ts
const BASE = "http://localhost:8000";

export interface InterruptPayload {
  action: string;
  args: Record<string, unknown>;
  description: string;
}

export interface ChatResponse {
  status: "interrupted" | "completed";
  thread_id: string;
  interrupt?: InterruptPayload;
  messages?: { content: string; type: string }[];
}

export async function sendMessage(
  message: string,
  threadId?: string
): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  return res.json();
}

export async function resumeExecution(
  threadId: string,
  decision: Record<string, unknown>
): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, resume: decision }),
  });
  return res.json();
}

export async function fetchState(threadId: string): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/state/${threadId}`);
  return res.json();
}