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

  send(
    content: string,
    opts: { model?: string; provider?: string; taskType?: string } = {},
  ): void {
    this.ws?.send(
      JSON.stringify({
        type: "user_message",
        content,
        task_type: opts.taskType ?? "reasoning",
        model: opts.model,
        provider: opts.provider,
      }),
    );
  }

  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}

// --- Orchestrated run socket: streams plan / step / token / done events. ---
export interface RunEventHandlers {
  onEvent: (event: Record<string, unknown> & { type: string }) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export class RunSocket {
  private ws: WebSocket | null = null;

  constructor(
    private sessionId: string,
    private handlers: RunEventHandlers,
  ) {}

  connect(): void {
    const ws = new WebSocket(`${WS_BASE}/ws/run/${this.sessionId}`);
    this.ws = ws;
    ws.onopen = () => this.handlers.onOpen?.();
    ws.onclose = () => this.handlers.onClose?.();
    ws.onmessage = (e) => this.handlers.onEvent(JSON.parse(e.data));
  }

  start(goal: string): void {
    this.ws?.send(JSON.stringify({ goal }));
  }

  close(): void {
    this.ws?.close();
    this.ws = null;
  }
}
