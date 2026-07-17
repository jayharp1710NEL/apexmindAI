"use client";

import { useEffect, useRef, useState } from "react";
import { ModelOption, createSession, listModels, sendFeedback } from "@/lib/api";
import { ChatSocket } from "@/lib/ws";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  pending?: boolean;
  model?: string;
}

function FeedbackButtons({
  prompt,
  answer,
  model,
}: {
  prompt: string;
  answer: string;
  model?: string;
}) {
  const [done, setDone] = useState<"up" | "down" | null>(null);
  if (done)
    return (
      <span className="mt-1 text-xs text-slate-500">
        {done === "up" ? "✓ saved as a good example" : "✓ correction saved"}
      </span>
    );
  return (
    <div className="mt-1 flex gap-2 text-xs text-slate-500">
      <button
        title="Good answer — save as training example"
        onClick={async () => {
          await sendFeedback({ prompt, answer, rating: "up", model });
          setDone("up");
        }}
        className="hover:text-emerald-400"
      >
        👍
      </button>
      <button
        title="Bad answer — give the correct one"
        onClick={async () => {
          const correction = window.prompt("What's the better answer?") ?? "";
          if (!correction) return;
          await sendFeedback({ prompt, answer, rating: "down", correction, model });
          setDone("down");
        }}
        className="hover:text-rose-400"
      >
        👎
      </button>
    </div>
  );
}

export default function ChatPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [picked, setPicked] = useState<string>("");
  const socketRef = useRef<ChatSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const pickedRef = useRef("");

  useEffect(() => {
    pickedRef.current = picked;
  }, [picked]);

  useEffect(() => {
    listModels().then((m) => {
      setModels(m);
      if (m.length) setPicked(`${m[0].provider}:${m[0].id}`);
    });
  }, []);

  // Create a session and open the WebSocket once.
  useEffect(() => {
    let socket: ChatSocket | null = null;
    (async () => {
      const sess = await createSession("Chat");
      setSessionId(sess.id);
      socket = new ChatSocket(sess.id, {
        onOpen: () => setConnected(true),
        onClose: () => setConnected(false),
        onStart: () =>
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              content: "",
              pending: true,
              model: pickedRef.current.split(":").slice(1).join(":") || "auto",
            },
          ]),
        onToken: (t) =>
          setMessages((m) => {
            // Pure update — never mutate existing objects (React 18 StrictMode
            // runs updaters twice in dev; mutating would double the text).
            const last = m[m.length - 1];
            if (!last?.pending) return m;
            const updated = { ...last, content: last.content + t };
            return [...m.slice(0, -1), updated];
          }),
        onDone: () => {
          setStreaming(false);
          setMessages((m) =>
            m.map((x) => (x.pending ? { ...x, pending: false } : x)),
          );
        },
        onError: (detail) => {
          setStreaming(false);
          setMessages((m) => [
            ...m,
            { role: "assistant", content: `⚠️ ${detail}` },
          ]);
        },
      });
      socket.connect();
      socketRef.current = socket;
    })();
    return () => socket?.close();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function send() {
    const text = input.trim();
    if (!text || !socketRef.current || streaming) return;
    setMessages((m) => [...m, { role: "user", content: text }]);
    const [provider, ...rest] = picked.split(":");
    socketRef.current.send(text, picked ? { provider, model: rest.join(":") } : {});
    setStreaming(true);
    setInput("");
  }

  return (
    <main className="mx-auto flex h-[calc(100vh-49px)] max-w-3xl flex-col p-4">
      <header className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h1 className="text-lg font-semibold">ApexMind · Chat</h1>
        <div className="flex items-center gap-3">
          {models.length > 0 && (
            <select
              value={picked}
              onChange={(e) => setPicked(e.target.value)}
              className="rounded bg-slate-800 px-2 py-1 text-xs outline-none"
            >
              {models.map((m) => (
                <option key={`${m.provider}:${m.id}`} value={`${m.provider}:${m.id}`}>
                  {m.label}
                </option>
              ))}
            </select>
          )}
          <span
            className={`text-xs ${connected ? "text-emerald-400" : "text-slate-500"}`}
          >
            {connected ? "● connected" : "○ connecting…"}
          </span>
        </div>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto py-4">
        {messages.length === 0 && (
          <p className="mt-10 text-center text-sm text-slate-500">
            Say hello to start. Responses stream token-by-token.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
                m.role === "user"
                  ? "bg-sky-600 text-white"
                  : "bg-slate-800 text-slate-100"
              }`}
            >
              {m.content}
              {m.pending && <span className="animate-pulse">▌</span>}
            </div>
            {m.role === "assistant" && m.model && (
              <span className="mt-1 text-[11px] text-slate-500">via {m.model}</span>
            )}
            {m.role === "assistant" && !m.pending && m.content && (
              <FeedbackButtons
                answer={m.content}
                prompt={messages[i - 1]?.content ?? ""}
                model={m.model}
              />
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2 border-t border-slate-800 pt-3">
        <input
          className="flex-1 rounded-lg bg-slate-800 px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-sky-500"
          placeholder="Message ApexMind…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={!sessionId}
        />
        <button
          onClick={send}
          disabled={!connected || streaming || !input.trim()}
          className="rounded-lg bg-sky-500 px-5 py-2 text-sm font-medium text-white transition hover:bg-sky-400 disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </main>
  );
}
