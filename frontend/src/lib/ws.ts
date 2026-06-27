// Thin WebSocket chat client. Server -> client events are discriminated by `type`.

import { WS_BASE } from "./api";

export type ServerEvent =
  | { type: "start" }
  | { type: "token"; content: string }
  | { type: "done"; message_id: string }
  | { type: "error"; detail: string };

export interface ChatSocketHandlers {
  onStart?: () => void;
  onToken?: (text: string) => void;
  onDone?: (messageId: string) => void;
  onError?: (detail: string) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export class ChatSocket {
  private ws: WebSocket | null = null;

  constructor(
    private sessionId: string,
    private handlers: ChatSocketHandlers,
  ) {}

  connect(): void {
    const ws = new WebSocket(`${WS_BASE}/ws/chat/${this.sessionId}`);
    this.ws = ws;
    ws.onopen = () => this.handlers.onOpen?.();
    ws.onclose = () => this.handlers.onClose?.();
    ws.onmessage = (e) => {
      const ev = JSON.parse(e.data) as ServerEvent;
      switch (ev.type) {
        case "start":
          this.handlers.onStart?.();
          break;
        case "token":
          this.handlers.onToken?.(ev.content);
          break;
        case "done":
          this.handlers.onDone?.(ev.message_id);
          break;
        case "error":
          this.handlers.onError?.(ev.detail);
          break;
      }
    };
  }

  send(content: string, taskType = "reasoning"): void {
    this.ws?.send(
      JSON.stringify({ type: "user_message", content, task_type: taskType }),
    );
  }

  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}
