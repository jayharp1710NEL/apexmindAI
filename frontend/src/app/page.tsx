import Link from "next/link";

const TILES = [
  { href: "/chat", title: "Chat", desc: "Streaming chat; every answer is critiqued." },
  { href: "/runs", title: "Runs", desc: "Plan-based goals under budget, with E-STOP." },
  { href: "/documents", title: "Documents", desc: "Ask your docs; answers cite chunks." },
  { href: "/memory", title: "Memory", desc: "Durable project facts you control." },
  { href: "/benchmarks", title: "Benchmarks", desc: "Objective pass/fail suite." },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-4xl p-8">
      <header className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">ApexMind AI</h1>
        <p className="mt-3 text-slate-400">
          Model-agnostic AI agent command center — safety-first, fully audited.
        </p>
      </header>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {TILES.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="rounded-xl border border-slate-800 p-5 transition hover:border-sky-500 hover:bg-slate-900"
          >
            <div className="text-lg font-semibold">{t.title}</div>
            <div className="mt-1 text-sm text-slate-400">{t.desc}</div>
          </Link>
        ))}
      </div>

      <p className="mt-10 text-center text-xs text-slate-500">
        Models reached only via the router · Level ≥3 actions pause for approval ·
        Level 5 refused · every model & tool call audited
      </p>
    </main>
  );
}
