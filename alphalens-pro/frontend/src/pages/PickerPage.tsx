// Stock Picker: Wochen-Picks (Quant-Ranking + Regime + optionaler KI-Kommentar)
// und die ehrliche, kumulative Historie aller bisherigen Wochen vs. Benchmark.
import { useCallback, useEffect, useState } from "react";
import { fmt } from "../lib/api";
import RegimeBanner from "../components/RegimeBanner";
import ScoreBar from "../components/ScoreBar";

type Pick = {
  id: number;
  ts_utc: string;
  ticker: string;
  probability: number | null;
  payload: {
    rank?: number;
    composite?: number;
    pillars?: Record<string, number>;
    risk_score?: number;
    entry?: number;
    stop?: number | null;
    sizing?: { final_pct?: number; steps?: string };
    calibration?: { calibrated?: boolean; label?: string };
    ai?: { analysis?: string; skipped?: string };
  };
  outcome: { result?: string; return_pct?: number; success?: boolean } | null;
};

type Week = {
  week: string;
  n: number;
  n_closed: number;
  avg_return_pct: number | null;
  hit_rate: number | null;
  benchmark_return_pct: number | null;
  picks: Pick[];
};

export default function PickerPage({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [weeks, setWeeks] = useState<Week[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    fetch("/api/picks")
      .then((r) => r.json())
      .then((d: { weeks: Week[] }) => setWeeks(d.weeks))
      .catch(() => {});
  }, []);
  useEffect(load, [load]);

  const runNow = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const r = await fetch("/api/picks/run", { method: "POST" });
      const data = await r.json();
      setMessage(data.skipped
        ? `Übersprungen: ${data.skipped}`
        : `${data.created} Picks für ${data.week} erzeugt (Regime: ${data.regime}).`);
      load();
    } catch {
      setMessage("Pick-Lauf fehlgeschlagen — Backend-Log prüfen.");
    } finally {
      setBusy(false);
    }
  };

  const current = weeks[0];
  const history = weeks.slice(1);

  return (
    <div className="space-y-5">
      <RegimeBanner />
      <div className="flex items-center gap-3">
        <button
          onClick={runNow}
          disabled={busy}
          className="rounded-md border border-accent/50 bg-accent/10 px-4 py-2 text-sm font-medium text-accent hover:bg-accent/20 disabled:opacity-50"
        >
          {busy ? "läuft…" : "Wochen-Picks jetzt erzeugen"}
        </button>
        <span className="text-xs text-gray-500">
          läuft sonst montags vor US-Open · idempotent pro Kalenderwoche
        </span>
      </div>
      {message && <div className="text-sm text-gray-400">{message}</div>}

      {!current ? (
        <div className="rounded-lg border border-line bg-panel p-5 text-sm text-gray-400">
          Noch keine Picks. Der Picker wählt die Top-10 nach Composite Score (Minimum 55) —
          liefert das Universum keine Kandidaten über der Schwelle, gibt es ehrlich keine
          Picks statt aufgefüllter Listen.
        </div>
      ) : (
        <section>
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            Picks {current.week}
            {current.avg_return_pct !== null &&
              ` · Ø ${fmt(current.avg_return_pct, 2)} % (${current.n_closed}/${current.n} geschlossen)`}
          </h2>
          <div className="space-y-3">
            {current.picks.map((p) => (
              <div key={p.id} className="rounded-lg border border-line bg-panel p-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="w-8 text-center font-mono text-sm text-gray-500">
                    #{p.payload.rank}
                  </span>
                  <button
                    onClick={() => onSelect(p.ticker)}
                    className="text-base font-semibold text-accent hover:underline"
                  >
                    {p.ticker}
                  </button>
                  <span className="text-sm tabular-nums">
                    Score <span className="font-semibold">{fmt(p.payload.composite ?? null, 1)}</span>
                  </span>
                  <span className="text-xs text-gray-500 tabular-nums">
                    Risiko {fmt(p.payload.risk_score ?? null, 1)}/10
                  </span>
                  <span
                    className="text-xs text-gray-500 tabular-nums"
                    title={p.payload.sizing?.steps ?? ""}
                  >
                    Größe {fmt(p.payload.sizing?.final_pct ?? null, 1)} % ⓘ
                  </span>
                  <span className="text-xs text-gray-500 tabular-nums"
                        title={p.payload.calibration?.label ?? ""}>
                    P(Erfolg) {p.probability !== null ? `${(p.probability * 100).toFixed(0)} %` : "–"}
                    {p.payload.calibration && !p.payload.calibration.calibrated && (
                      <span className="ml-1 text-yellow-400">unkalibriert</span>
                    )}
                  </span>
                  <span className="ml-auto">
                    {p.outcome ? (
                      <span className={`rounded px-2 py-0.5 text-xs ${
                        p.outcome.success ? "bg-gain/15 text-gain" : "bg-loss/15 text-loss"}`}>
                        {p.outcome.result} · {fmt(p.outcome.return_pct ?? null, 2)} %
                      </span>
                    ) : (
                      <span className="rounded bg-panel-hover px-2 py-0.5 text-xs text-gray-400">
                        offen
                      </span>
                    )}
                  </span>
                </div>
                {p.payload.pillars && (
                  <div className="mt-2 flex gap-5 text-xs text-gray-500">
                    {Object.entries(p.payload.pillars).map(([name, value]) => (
                      <span key={name} className="flex items-center gap-1.5">
                        {name.slice(0, 1).toUpperCase()} <ScoreBar score={value} />
                      </span>
                    ))}
                  </div>
                )}
                {p.payload.ai?.analysis ? (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-xs text-accent hover:underline">
                      KI-Deep-Dive (Kommentar zur Quant-Auswahl)
                    </summary>
                    <pre className="mt-2 whitespace-pre-wrap rounded bg-surface p-3 text-xs text-gray-300">
                      {p.payload.ai.analysis}
                    </pre>
                  </details>
                ) : (
                  p.payload.ai?.skipped && (
                    <div className="mt-2 text-[11px] text-gray-600">
                      KI-Kommentar übersprungen: {p.payload.ai.skipped}
                    </div>
                  )
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {history.length > 0 && (
        <section>
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            Historie — kumulativ und ehrlich, gegen S&P 500
          </h2>
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[10px] uppercase tracking-wider text-gray-500">
                  <th className="px-4 py-2.5">Woche</th>
                  <th className="px-4 py-2.5">Picks</th>
                  <th className="px-4 py-2.5">geschlossen</th>
                  <th className="px-4 py-2.5">Hit-Rate</th>
                  <th className="px-4 py-2.5">Ø-Rendite</th>
                  <th className="px-4 py-2.5">S&P 500</th>
                </tr>
              </thead>
              <tbody>
                {history.map((w) => (
                  <tr key={w.week} className="border-b border-line/50 last:border-0">
                    <td className="px-4 py-2 font-mono text-xs">{w.week}</td>
                    <td className="px-4 py-2 tabular-nums">{w.n}</td>
                    <td className="px-4 py-2 tabular-nums">{w.n_closed}</td>
                    <td className="px-4 py-2 tabular-nums">
                      {w.hit_rate !== null ? `${(w.hit_rate * 100).toFixed(0)} %` : "–"}
                    </td>
                    <td className={`px-4 py-2 tabular-nums ${
                      (w.avg_return_pct ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
                      {w.avg_return_pct !== null ? `${fmt(w.avg_return_pct, 2)} %` : "–"}
                    </td>
                    <td className="px-4 py-2 tabular-nums text-gray-400">
                      {w.benchmark_return_pct !== null
                        ? `${fmt(w.benchmark_return_pct, 2)} %`
                        : "– (keine ^GSPC-Daten)"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
