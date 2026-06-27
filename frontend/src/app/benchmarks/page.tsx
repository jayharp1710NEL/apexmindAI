"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BenchmarkRun, runBenchmarks } from "@/lib/api";

export default function BenchmarksPage() {
  const [run, setRun] = useState<BenchmarkRun | null>(null);
  const [busy, setBusy] = useState(false);

  async function go() {
    setBusy(true);
    try {
      setRun(await runBenchmarks());
    } finally {
      setBusy(false);
    }
  }

  const chartData = run
    ? Object.entries(run.summary.by_category).map(([category, v]) => ({
        category,
        passed: v.passed,
        failed: v.failed,
      }))
    : [];

  return (
    <main className="mx-auto max-w-4xl p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">ApexMind · Benchmarks</h1>
          <p className="mt-1 text-sm text-slate-400">
            Objective pass/fail checks across coding, math, sandbox, safety,
            injection, permission, memory, and audit.
          </p>
        </div>
        <button
          onClick={go}
          disabled={busy}
          className="rounded-lg bg-sky-500 px-5 py-2 text-sm font-medium text-white hover:bg-sky-400 disabled:opacity-40"
        >
          {busy ? "Running…" : "Run suite"}
        </button>
      </div>

      {run && (
        <>
          <div className="mt-5 flex gap-4 text-sm">
            <span className="rounded bg-slate-800 px-3 py-1">
              Total <b>{run.summary.scored}</b>
            </span>
            <span className="rounded bg-emerald-900/50 px-3 py-1 text-emerald-300">
              Passed <b>{run.summary.passed}</b>
            </span>
            <span className="rounded bg-rose-900/50 px-3 py-1 text-rose-300">
              Failed <b>{run.summary.failed}</b>
            </span>
            {run.summary.skipped > 0 && (
              <span className="rounded bg-slate-800 px-3 py-1 text-slate-400">
                Skipped <b>{run.summary.skipped}</b>
              </span>
            )}
          </div>

          <div className="mt-6 h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="category" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
                />
                <Legend />
                <Bar dataKey="passed" stackId="a" fill="#10b981" />
                <Bar dataKey="failed" stackId="a" fill="#f43f5e" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <table className="mt-6 w-full text-sm">
            <thead className="text-left text-slate-400">
              <tr>
                <th className="py-2">Test</th>
                <th>Category</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {run.results.map((r) => (
                <tr key={r.test_id} className="border-t border-slate-800">
                  <td className="py-2 font-mono text-xs">{r.test_id}</td>
                  <td className="text-slate-400">{r.category}</td>
                  <td>
                    {r.passed === null ? (
                      <span className="text-slate-500">skipped</span>
                    ) : r.passed ? (
                      <span className="text-emerald-400">✓ pass</span>
                    ) : (
                      <span className="text-rose-400">✗ fail</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </main>
  );
}
