"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  PendingApproval,
  getEstop,
  listApprovals,
  resolveApproval,
  setEstop,
} from "@/lib/api";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat" },
  { href: "/runs", label: "Runs" },
  { href: "/documents", label: "Documents" },
  { href: "/memory", label: "Memory" },
  { href: "/benchmarks", label: "Benchmarks" },
];

export default function NavBar() {
  const pathname = usePathname();
  const [engaged, setEngaged] = useState(false);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    setEngaged((await getEstop()).engaged);
    setApprovals(await listApprovals());
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000); // live safety state
    return () => clearInterval(t);
  }, [refresh]);

  async function toggleEstop() {
    await setEstop(!engaged);
    await refresh();
  }

  async function decide(id: string, approved: boolean) {
    await resolveApproval(id, approved);
    await refresh();
  }

  return (
    <header className="sticky top-0 z-50 flex items-center gap-1 border-b border-slate-800 bg-slate-950/90 px-4 py-2 backdrop-blur">
      <Link href="/" className="mr-3 font-semibold tracking-tight">
        Apex<span className="text-sky-400">Mind</span>
      </Link>

      <nav className="flex flex-1 flex-wrap gap-1 text-sm">
        {LINKS.slice(1).map((l) => {
          const active = pathname === l.href;
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded px-3 py-1 transition ${
                active
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>

      {/* pending approvals (Level >=3) */}
      {approvals.length > 0 && (
        <div className="relative mr-2">
          <button
            onClick={() => setOpen((o) => !o)}
            className="rounded bg-amber-500/20 px-3 py-1 text-xs font-medium text-amber-300 hover:bg-amber-500/30"
          >
            {approvals.length} approval{approvals.length > 1 ? "s" : ""}
          </button>
          {open && (
            <div className="absolute right-0 mt-2 w-72 rounded-lg border border-slate-700 bg-slate-900 p-2 text-xs shadow-xl">
              {approvals.map((a) => (
                <div key={a.id} className="border-b border-slate-800 py-2 last:border-0">
                  <div className="text-slate-200">
                    {a.tool_name} · Level {a.level}
                  </div>
                  <div className="mt-1 flex gap-2">
                    <button
                      onClick={() => decide(a.id, true)}
                      className="rounded bg-emerald-600 px-2 py-0.5 text-white"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => decide(a.id, false)}
                      className="rounded bg-rose-600 px-2 py-0.5 text-white"
                    >
                      Deny
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* emergency stop — reachable on every page */}
      <button
        onClick={toggleEstop}
        title={engaged ? "System halted — click to resume" : "Halt all tool actions"}
        className={`rounded px-3 py-1 text-xs font-bold transition ${
          engaged
            ? "animate-pulse bg-rose-600 text-white"
            : "bg-slate-800 text-rose-300 hover:bg-rose-600 hover:text-white"
        }`}
      >
        {engaged ? "● STOPPED — RESUME" : "E-STOP"}
      </button>
    </header>
  );
}
