"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

interface Fact {
  id: string;
  key: string;
  value: string;
  confidence: number;
  scope: string;
  updated_at: string | null;
}

export default function MemoryPage() {
  const [facts, setFacts] = useState<Fact[]>([]);

  async function refresh() {
    const res = await fetch(`${API_BASE}/api/memory`);
    setFacts(await res.json());
  }
  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  async function remove(id: string) {
    await fetch(`${API_BASE}/api/memory/${id}`, { method: "DELETE" });
    await refresh();
  }

  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-xl font-semibold">ApexMind · Memory</h1>
      <p className="mt-1 text-sm text-slate-400">
        Durable project facts the system remembers and injects as context. Facts are
        added conservatively by the Memory step. You stay in control — delete any.
      </p>

      {facts.length === 0 ? (
        <p className="mt-8 text-center text-sm text-slate-500">No facts stored yet.</p>
      ) : (
        <ul className="mt-5 space-y-2">
          {facts.map((f) => (
            <li
              key={f.id}
              className="flex items-center justify-between rounded-lg border border-slate-800 p-3"
            >
              <div>
                <div className="text-sm">
                  <span className="text-slate-400">{f.key}:</span> {f.value}
                </div>
                <div className="text-xs text-slate-500">
                  confidence {Math.round(f.confidence * 100)}% · {f.scope}
                </div>
              </div>
              <button
                onClick={() => remove(f.id)}
                className="rounded bg-rose-600/80 px-3 py-1 text-xs text-white hover:bg-rose-600"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
