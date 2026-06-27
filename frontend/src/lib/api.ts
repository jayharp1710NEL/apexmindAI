// REST + WS base URLs, derived from NEXT_PUBLIC_API_BASE.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export const WS_BASE = API_BASE.replace(/^http/, "ws");

export interface SessionOut {
  id: string;
  title: string | null;
  created_at: string;
}

export interface MessageOut {
  id: string;
  role: string;
  content: string;
  meta?: Record<string, unknown> | null;
  created_at: string;
}

export async function createSession(title?: string): Promise<SessionOut> {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`createSession failed: ${res.status}`);
  return res.json();
}

export async function getMessages(sessionId: string): Promise<MessageOut[]> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/messages`);
  if (!res.ok) throw new Error(`getMessages failed: ${res.status}`);
  return res.json();
}
