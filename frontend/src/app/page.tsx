import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-8 p-8 text-center">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">ApexMind AI</h1>
        <p className="mt-3 text-slate-400">
          Model-agnostic AI agent command center.
        </p>
      </div>
      <Link
        href="/chat"
        className="rounded-lg bg-sky-500 px-6 py-3 font-medium text-white transition hover:bg-sky-400"
      >
        Open chat →
      </Link>
      <p className="text-xs text-slate-500">
        MVP build · streaming chat over WebSocket · every model call audited
      </p>
    </main>
  );
}
