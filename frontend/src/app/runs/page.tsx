"use client";

import { useEffect, useRef, useState } from "react";
import { createSession } from "@/lib/api";
import { RunSocket } from "@/lib/ws";

interface PlanStep {
  id: number;
  description: string;
  tool: string;
  tool_level: number;
}
interface StepResult {
  id: number;
  status: string;
  stdout?: string;
  reason?: string;
}

export default function RunsPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [goal, setGoal] = useState("");
  const [plan, setPlan] = useState<PlanStep[]>([]);
  const [results, setResults] = useState<Record<number, StepResult>>({});
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<string>("");
  const [running, setRunning] = useState(false);
  const sockRef = useRef<RunSocket | null>(null);

  useEffect(() => {
    let sock: RunSocket | null = null;
    (async () => {
      const sess = await createSession("Run");
      setSessionId(sess.id);
      sock = new RunSocket(sess.id, {
        onEvent: (ev) => {
          switch (ev.type) {
            case "plan":
              setPlan(((ev.plan as { steps: PlanStep[] }).steps) ?? []);
              setStatus("planning complete");
              break;
            case "step_start":
              setStatus(`running step ${ev.id}`);
              break;
            case "step_result":
              setResults((r) => ({ ...r, [ev.id as number]: ev as unknown as StepResult }));
              break;
            case "token":
              setAnswer((a) => a + (ev.content as string));
              break;
            case "halted":
              setStatus(`halted: ${ev.reason}`);
              setRunning(false);
              break;
            case "done":
              setStatus(`done · ${ev.steps_used} steps · $${ev.cost_usd}`);
              setRunning(false);
              break;
            case "error":
              setStatus(`error: ${ev.detail}`);
              setRunning(false);
              break;
          }
        },
      });
      sock.connect();
      sockRef.current = sock;
    })();
    return () => sock?.close();
  }, []);

  function start() {
    if (!goal.trim() || !sockRef.current || running) return;
    setPlan([]);
    setResults({});
    setAnswer("");
    setStatus("planning…");
    setRunning(true);
    sockRef.current.start(goal.trim());
  }

  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-xl font-semibold">ApexMind · Runs</h1>
      <p className="mt-1 text-sm text-slate-400">
        Give a complex goal. It plans, executes steps under budget (with E-STOP
        between steps), and streams the final answer. Tool steps show real sandbox
        output.
      </p>

      <div className="mt-4 flex gap-2">
        <input
          className="flex-1 rounded-lg bg-slate-800 px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-sky-500"
          placeholder="e.g. Compute the 10th Fibonacci number with code and explain it"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && start()}
          disabled={!sessionId}
        />
        <button
          onClick={start}
          disabled={!sessionId || running || !goal.trim()}
          className="rounded-lg bg-sky-500 px-5 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-40"
        >
          Run
        </button>
      </div>

      {status && <p className="mt-3 text-xs text-amber-300">{status}</p>}

      {plan.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold text-slate-300">Plan</h2>
          <ol className="mt-2 space-y-2">
            {plan.map((s) => {
              const r = results[s.id];
              return (
                <li key={s.id} className="rounded-lg border border-slate-800 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm">
                      <span className="text-slate-500">#{s.id}</span>{" "}
                      {s.description}
                    </span>
                    <span className="text-xs text-slate-500">
                      {s.tool !== "none" ? `${s.tool} · L${s.tool_level}` : "agent"}
                      {r && ` · ${r.status}`}
                    </span>
                  </div>
                  {r?.stdout && (
                    <pre className="mt-2 overflow-x-auto rounded bg-black/50 p-2 text-xs text-emerald-300">
                      {r.stdout}
                    </pre>
                  )}
                  {r?.reason && (
                    <p className="mt-1 text-xs text-rose-300">{r.reason}</p>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {answer && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold text-slate-300">Answer</h2>
          <div className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-800 p-4 text-sm">
            {answer}
          </div>
        </section>
      )}
    </main>
  );
}
