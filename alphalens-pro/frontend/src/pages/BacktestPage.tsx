// Backtesting Playground (USP 1): Point-in-Time, Walk-Forward, ehrliche Kosten.
// Jedes Ergebnis trägt Konfidenzintervalle, Overfitting-Warnungen und das
// verpflichtende Data-Caveats-Panel — Zahlen ohne Kontext gibt es hier nicht.
import { useCallback, useEffect, useState } from "react";
import { fmt } from "../lib/api";
import EquityChart, { type EquityPoint } from "../components/EquityChart";

type BacktestResult = {
  strategy: string;
  report_id?: number;
  config: Record<string, unknown>;
  metrics: {
    total_return_pct: number | null;
    cagr: number | null;
    cagr_ci95: [number, number] | null;
    sharpe: number | null;
    sharpe_ci95: [number, number] | null;
    sortino: number | null;
    max_drawdown: number | null;
    hit_rate: number | null;
    n_trades: number;
    annual_turnover: number | null;
    total_costs_eur?: number;
    n_days: number;
  };
  equity: EquityPoint[];
  benchmark: EquityPoint[] | null;
  trades?: { ticker: string; entry_date: string; result: string; return_pct: number }[];
  walk_forward?: {
    fold: number; test_from: string; n_train: number; n_test: number;
    train_hit_rate: number | null; test_hit_rate: number; test_avg_return_pct: number;
  }[];
  caveats: string[];
  warnings: string[];
};

type SavedReport = { id: number; name: string; strategy: string; created_at: string };

function MetricCard({ label, value, ci, tone }: {
  label: string; value: string; ci?: string; tone?: "gain" | "loss";
}) {
  return (
    <div className="rounded-lg border border-line bg-panel px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-gray-500">{label}</div>
      <div className={`mt-1 text-lg font-semibold tabular-nums ${
        tone === "gain" ? "text-gain" : tone === "loss" ? "text-loss" : ""}`}>
        {value}
      </div>
      {ci && <div className="text-[10px] tabular-nums text-gray-500">95%-KI: {ci}</div>}
    </div>
  );
}

export default function BacktestPage() {
  const [strategy, setStrategy] = useState("score_ranking");
  const [start, setStart] = useState("2022-01-01");
  const [end, setEnd] = useState("");
  const [topN, setTopN] = useState("10");
  const [rebalance, setRebalance] = useState("monthly");
  const [signalType, setSignalType] = useState("breakout");
  const [costBps, setCostBps] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [reports, setReports] = useState<SavedReport[]>([]);

  const loadReports = useCallback(() => {
    fetch("/api/backtest/reports").then((r) => r.json()).then(setReports).catch(() => {});
  }, []);
  useEffect(loadReports, [loadReports]);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        strategy, start, rebalance, top_n: Number(topN), signal_type: signalType,
      };
      if (end) body.end = end;
      if (costBps) body.cost_bps_per_side = Number(costBps);
      const r = await fetch("/api/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail ?? `HTTP ${r.status}`);
      setResult(data as BacktestResult);
      loadReports();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const loadReport = async (id: number) => {
    const r = await fetch(`/api/backtest/reports/${id}`);
    if (r.ok) setResult((await r.json()) as BacktestResult);
  };

  const inputClass =
    "rounded-md border border-line bg-surface px-3 py-1.5 text-sm outline-none " +
    "placeholder:text-gray-600 focus:border-accent";
  const m = result?.metrics;

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-line bg-panel p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-gray-500">
            Strategie
            <select value={strategy} onChange={(e) => setStrategy(e.target.value)}
                    className={`${inputClass} mt-1 block`}>
              <option value="score_ranking">Score-Ranking (Top-N Composite)</option>
              <option value="signal_setup">Signal-Setup (historisch)</option>
            </select>
          </label>
          {strategy === "score_ranking" ? (
            <>
              <label className="text-xs text-gray-500">
                Top N
                <input value={topN} onChange={(e) => setTopN(e.target.value)} type="number"
                       className={`${inputClass} mt-1 block w-20`} />
              </label>
              <label className="text-xs text-gray-500">
                Rebalancing
                <select value={rebalance} onChange={(e) => setRebalance(e.target.value)}
                        className={`${inputClass} mt-1 block`}>
                  <option value="weekly">wöchentlich</option>
                  <option value="monthly">monatlich</option>
                  <option value="quarterly">quartalsweise</option>
                </select>
              </label>
            </>
          ) : (
            <label className="text-xs text-gray-500">
              Setup
              <select value={signalType} onChange={(e) => setSignalType(e.target.value)}
                      className={`${inputClass} mt-1 block`}>
                <option value="breakout">breakout</option>
                <option value="mean_reversion">mean_reversion</option>
                <option value="pullback_ma50">pullback_ma50</option>
              </select>
            </label>
          )}
          <label className="text-xs text-gray-500">
            Von
            <input value={start} onChange={(e) => setStart(e.target.value)} type="date"
                   className={`${inputClass} mt-1 block`} />
          </label>
          <label className="text-xs text-gray-500">
            Bis (leer = heute)
            <input value={end} onChange={(e) => setEnd(e.target.value)} type="date"
                   className={`${inputClass} mt-1 block`} />
          </label>
          <label className="text-xs text-gray-500" title="halber Spread + Slippage">
            Kosten bp/Seite
            <input value={costBps} onChange={(e) => setCostBps(e.target.value)} type="number"
                   placeholder="11" className={`${inputClass} mt-1 block w-24`} />
          </label>
          <button onClick={run} disabled={busy}
                  className="rounded-md border border-accent/50 bg-accent/10 px-4 py-2 text-sm font-medium text-accent hover:bg-accent/20 disabled:opacity-50">
            {busy ? "rechnet… (kann Minuten dauern)" : "Backtest starten"}
          </button>
        </div>
      </div>

      {error && <div className="rounded-lg border border-loss/40 bg-loss/10 p-3 text-sm text-loss">{error}</div>}

      {result && m && (
        <>
          {result.warnings.length > 0 && (
            <div className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-4">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-yellow-400">
                ⚠ Overfitting- / Datenwarnungen
              </div>
              <ul className="space-y-1 text-sm text-yellow-200/80">
                {result.warnings.map((w, i) => <li key={i}>• {w}</li>)}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <MetricCard label="Gesamtrendite"
                        value={m.total_return_pct !== null ? `${fmt(m.total_return_pct, 1)} %` : "–"}
                        tone={(m.total_return_pct ?? 0) >= 0 ? "gain" : "loss"} />
            <MetricCard label="CAGR"
                        value={m.cagr !== null ? `${fmt(m.cagr * 100, 1)} %` : "–"}
                        ci={m.cagr_ci95 ? `${fmt(m.cagr_ci95[0] * 100, 1)} … ${fmt(m.cagr_ci95[1] * 100, 1)} %` : undefined} />
            <MetricCard label="Sharpe" value={fmt(m.sharpe, 2)}
                        ci={m.sharpe_ci95 ? `${fmt(m.sharpe_ci95[0], 2)} … ${fmt(m.sharpe_ci95[1], 2)}` : undefined} />
            <MetricCard label="Sortino" value={fmt(m.sortino, 2)} />
            <MetricCard label="Max Drawdown"
                        value={m.max_drawdown !== null ? `${fmt(m.max_drawdown * 100, 1)} %` : "–"}
                        tone="loss" />
            <MetricCard label="Hit-Rate"
                        value={m.hit_rate !== null ? `${fmt(m.hit_rate * 100, 0)} % (${m.n_trades})` : `– (${m.n_trades})`} />
            <MetricCard label={m.total_costs_eur !== undefined ? "Kosten" : "Turnover p.a."}
                        value={m.total_costs_eur !== undefined
                          ? `${fmt(m.total_costs_eur, 0)} €`
                          : fmt(m.annual_turnover, 2)} />
          </div>

          <div className="rounded-lg border border-line bg-panel p-4">
            <EquityChart equity={result.equity} benchmark={result.benchmark} />
          </div>

          {result.walk_forward && result.walk_forward.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-line bg-panel">
              <div className="border-b border-line px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                Walk-Forward: hält die Hit-Rate out-of-sample?
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-[10px] uppercase tracking-wider text-gray-500">
                    <th className="px-4 py-2">Fold</th>
                    <th className="px-4 py-2">Test ab</th>
                    <th className="px-4 py-2">Trades (Train/Test)</th>
                    <th className="px-4 py-2">Hit-Rate Train</th>
                    <th className="px-4 py-2">Hit-Rate Test (OOS)</th>
                    <th className="px-4 py-2">Ø-Rendite Test</th>
                  </tr>
                </thead>
                <tbody>
                  {result.walk_forward.map((f) => (
                    <tr key={f.fold} className="border-b border-line/50 last:border-0">
                      <td className="px-4 py-2 tabular-nums">{f.fold}</td>
                      <td className="px-4 py-2 font-mono text-xs">{f.test_from}</td>
                      <td className="px-4 py-2 tabular-nums">{f.n_train} / {f.n_test}</td>
                      <td className="px-4 py-2 tabular-nums">
                        {f.train_hit_rate !== null ? `${fmt(f.train_hit_rate * 100, 0)} %` : "–"}
                      </td>
                      <td className="px-4 py-2 tabular-nums font-semibold">
                        {fmt(f.test_hit_rate * 100, 0)} %
                      </td>
                      <td className={`px-4 py-2 tabular-nums ${
                        f.test_avg_return_pct >= 0 ? "text-gain" : "text-loss"}`}>
                        {fmt(f.test_avg_return_pct, 2)} %
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="rounded-lg border border-amber-600/40 bg-amber-500/5 p-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-400">
              Data Caveats — was in diesem Ergebnis steckt (und was nicht)
            </div>
            <ul className="space-y-1.5 text-[13px] leading-snug text-gray-400">
              {result.caveats.map((c, i) => <li key={i}>• {c}</li>)}
            </ul>
          </div>
        </>
      )}

      {reports.length > 0 && (
        <section>
          <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            Gespeicherte Reports
          </h2>
          <div className="flex flex-wrap gap-2">
            {reports.map((r) => (
              <button key={r.id} onClick={() => loadReport(r.id)}
                      className="rounded-md border border-line bg-panel px-3 py-1.5 text-xs text-gray-400 hover:border-accent hover:text-accent">
                #{r.id} {r.name} · {r.created_at.slice(0, 10)}
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
