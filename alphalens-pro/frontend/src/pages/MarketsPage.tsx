// Märkte: Markt-Zustand (VIX, Breadth, EURUSD, Indizes) + Composite-Ranking.
import { useEffect, useState } from "react";
import { api, fmt, type MarketMetric, type ScreenerRow } from "../lib/api";
import StatCard from "../components/StatCard";
import ScoreBar from "../components/ScoreBar";

const METRIC_LABELS: Record<string, { label: string; digits: number; sub?: string }> = {
  vix: { label: "VIX", digits: 1, sub: "implizite Volatilität S&P 500" },
  breadth_pct_above_ma200: { label: "Marktbreite", digits: 0, sub: "% Aktien über MA200" },
  eurusd: { label: "EUR/USD", digits: 4 },
  sp500_index: { label: "S&P 500", digits: 0 },
  eurostoxx_index: { label: "EuroStoxx 50", digits: 0 },
};

export default function MarketsPage({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [metrics, setMetrics] = useState<MarketMetric[]>([]);
  const [ranking, setRanking] = useState<ScreenerRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.marketState(), api.scores(25)])
      .then(([m, r]) => {
        setMetrics(m);
        setRanking(r);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
          Marktzustand
        </h2>
        {metrics.length === 0 ? (
          <div className="rounded-lg border border-line bg-panel p-5 text-sm text-gray-400">
            Noch keine Marktzustandsdaten. <span className="font-mono">make update</span>{" "}
            ausführen, um VIX, Marktbreite und EURUSD zu laden. (Das Regime-Gate in MS5 baut
            hierauf auf.)
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            {metrics.map((m) => {
              const meta = METRIC_LABELS[m.metric] ?? { label: m.metric, digits: 2 };
              return (
                <StatCard
                  key={m.metric}
                  label={meta.label}
                  value={fmt(m.value, meta.digits)}
                  sub={meta.sub ?? `Stand ${m.date}`}
                  tooltip={`Quelle: yfinance · Datum: ${m.date} · as_of: ${m.as_of.slice(0, 16)}`}
                />
              );
            })}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
          Composite-Ranking{" "}
          {ranking[0]?.score_date ? `(Stand ${ranking[0].score_date})` : ""}
        </h2>
        {error && <div className="text-sm text-loss">{error}</div>}
        {ranking.length === 0 && !error ? (
          <div className="rounded-lg border border-line bg-panel p-5 text-sm text-gray-400">
            Noch keine Scores berechnet — Teil des täglichen Updates
            (<span className="font-mono">make update</span>).
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[10px] uppercase tracking-wider text-gray-500">
                  <th className="px-4 py-2.5">#</th>
                  <th className="px-4 py-2.5">Ticker</th>
                  <th className="px-4 py-2.5">Composite</th>
                  <th className="px-4 py-2.5">Value</th>
                  <th className="px-4 py-2.5">Quality</th>
                  <th className="px-4 py-2.5">Momentum</th>
                  <th className="px-4 py-2.5">Growth</th>
                  <th className="px-4 py-2.5">Risiko</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((row, i) => (
                  <tr
                    key={row.ticker}
                    onClick={() => onSelect(row.ticker)}
                    className="cursor-pointer border-b border-line/50 transition-colors last:border-0 hover:bg-panel-hover"
                  >
                    <td className="px-4 py-2 tabular-nums text-gray-500">{i + 1}</td>
                    <td className="px-4 py-2 font-medium text-accent">{row.ticker}</td>
                    <td className="px-4 py-2 font-semibold tabular-nums">
                      {fmt(row.composite, 1)}
                    </td>
                    <td className="px-4 py-2"><ScoreBar score={row.value} /></td>
                    <td className="px-4 py-2"><ScoreBar score={row.quality} /></td>
                    <td className="px-4 py-2"><ScoreBar score={row.momentum} /></td>
                    <td className="px-4 py-2"><ScoreBar score={row.growth} /></td>
                    <td className="px-4 py-2 tabular-nums">{fmt(row.risk_score, 1)}/10</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
