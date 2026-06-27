"use client";

import { useEffect, useState } from "react";
import {
  DocumentOut,
  RagAnswer,
  listDocuments,
  ragQuery,
  uploadDocument,
} from "@/lib/api";

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentOut[]>([]);
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  async function refresh() {
    setDocs(await listDocuments());
  }
  useEffect(() => {
    refresh().catch(() => {});
  }, []);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setNote(`Uploading ${file.name}…`);
    try {
      const r = await uploadDocument(file);
      setNote(`Ingested ${file.name}: ${r.chunks} chunks`);
      await refresh();
    } catch (err) {
      setNote(`Upload failed: ${String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  async function ask() {
    if (!query.trim()) return;
    setBusy(true);
    setAnswer(null);
    try {
      setAnswer(await ragQuery(query.trim()));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-xl font-semibold">ApexMind · Documents</h1>
      <p className="mt-1 text-sm text-slate-400">
        Upload text, then ask questions. Answers cite source chunks as [n]; if
        nothing supports the answer, you get <b>Unverified</b>.
      </p>

      <div className="mt-4 flex items-center gap-3">
        <label className="cursor-pointer rounded-lg bg-slate-800 px-4 py-2 text-sm hover:bg-slate-700">
          <input type="file" accept=".txt,.md,text/*" className="hidden" onChange={onUpload} />
          Upload document
        </label>
        {note && <span className="text-xs text-amber-300">{note}</span>}
      </div>

      {docs.length > 0 && (
        <ul className="mt-4 space-y-1 text-sm text-slate-300">
          {docs.map((d) => (
            <li key={d.id} className="flex justify-between border-b border-slate-800 py-1">
              <span>{d.filename}</span>
              <span className="text-xs text-slate-500">{d.size_bytes ?? 0} bytes</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6 flex gap-2">
        <input
          className="flex-1 rounded-lg bg-slate-800 px-4 py-2 text-sm outline-none focus:ring-2 focus:ring-sky-500"
          placeholder="Ask about your documents…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask()}
        />
        <button
          onClick={ask}
          disabled={busy || !query.trim()}
          className="rounded-lg bg-sky-500 px-5 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-40"
        >
          Ask
        </button>
      </div>

      {answer && (
        <section className="mt-5 rounded-lg bg-slate-800 p-4">
          <p
            className={`whitespace-pre-wrap text-sm ${
              answer.grounded ? "" : "text-amber-300"
            }`}
          >
            {answer.answer}
          </p>
          {answer.citations.length > 0 && (
            <div className="mt-3 border-t border-slate-700 pt-2 text-xs text-slate-400">
              {answer.citations.map((c) => (
                <div key={c.n}>
                  [{c.n}] chunk {c.chunk_id.slice(0, 8)}…
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
