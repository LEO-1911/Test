// Signale ("SwingMax, aber ehrlich"): Regime-Banner + Signal-Karten mit
// Entry/Stop/Ziel, kalibrierter Wahrscheinlichkeit, Sizing-Herleitung und Why-Panel.
import { useCallback, useEffect, useState } from "react";
import { fmt } from "../lib/api";
import RegimeBanner from "../components/RegimeBanner";

type SignalView = {
  id: number;
  ts_utc: string;
  ticker: string;
  probability: number | null;
  payload: {
    signal_type?: string;
    entry?: number;
    stop?: number;
    target?: number;
    horizon_days?: number;
    why?: string[];
    sizing?: { final_pct?: number; steps?: string };
    calibration?: { label?: string; calibrated?: boolean };
    regime?: { regime?: string; factor?: number };
  };
  outcome: { result?: string; return_pct?: number; success?: boolean } | null;
};

export default function SignalsPage({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [signals, setSignals] = useState<SignalView[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    fetch("/api/signals")
      .then((r) => r.json())
      .then(setSignals)
      .catch(() => {});
  }, []);
  useEffect(load, [load]);

  const generateNow = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const r = await fetch("/api/signals/generate", { method: "POST" });
      const data = await r.json();
      setMessage(
        `Lauf abgeschlossen: ${data.stocks_checked} Aktien geprüft, ` +
          `${data.signals_created} neue Signale (Regime: ${data.regime}).`,
      );
      load();
    } catch {
      setMessage("Signal-Lauf fehlgeschlagen — Backend-Log prüfen.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      <RegimeBanner />

      <div className="flex items-center gap-3">
        <button
          onClick={generateNow}
          disabled={busy}
          className="rounded-md border border-accent/50 bg-accent/10 px-4 py-2 text-sm font-medium text-accent hover:bg-accent/20 disabled:opacity-50"
        >
          {busy ? "läuft…" : "Signal-Lauf jetzt starten"}
        </button>
        <span className="text-xs text-gray-500">
          läuft sonst automatisch im täglichen Update · earnings_momentum inaktiv bis MS8
        </span>
      </div>
      {message && <div className="text-sm text-gray-400">{message}</div>}

      {signals.length === 0 ? (
        <div className="rounded-lg border border-line bg-panel p-5 text-sm text-gray-400">
          Keine Signale im Ledger. Setups feuern nur, wenn alle Bedingungen erfüllt sind —
          kein Signal ist ein ehrliches Ergebnis, kein Fehler.
        </div>
      ) : (
        <div className="space-y-3">
          {signals.map((s) => (
            <div key={s.id} className="rounded-lg border border-line bg-panel p-4">
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={() => onSelect(s.ticker)}
                  className="text-base font-semibold text-accent hover:underline"
                >
                  {s.ticker}
                </button>
                <span className="rounded bg-accent/15 px-2 py-0.5 font-mono text-[11px] text-accent">
                  {s.payload.signal_type}
                </span>
                <span className="text-xs text-gray-500">
                  {s.ts_utc.replace("T", " ").slice(0, 16)} UTC · Ledger #{s.id}
                </span>
                <span className="ml-auto">
                  {s.outcome ? (
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        s.outcome.success ? "bg-gain/15 text-gain" : "bg-loss/15 text-loss"
                      }`}
                    >
                      {s.outcome.result} · {fmt(s.outcome.return_pct ?? null, 2)} %
                    </span>
                  ) : (
                    <span className="rounded bg-panel-hover px-2 py-0.5 text-xs text-gray-400">
                      offen
                    </span>
                  )}
                </span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-3 text-sm md:grid-cols-5">
                <div>
                  <div className="text-[10px] uppercase text-gray-500">Entry</div>
                  <div className="tabular-nums">{fmt(s.payload.entry ?? null, 2)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-gray-500">Stop (ATR)</div>
                  <div className="tabular-nums text-loss">{fmt(s.payload.stop ?? null, 2)}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase text-gray-500">Ziel</div>
                  <div className="tabular-nums text-gain">{fmt(s.payload.target ?? null, 2)}</div>
                </div>
                <div title={s.payload.calibration?.label ?? ""}>
                  <div className="text-[10px] uppercase text-gray-500">P(Erfolg)</div>
                  <div className="tabular-nums">
                    {s.probability !== null ? `${(s.probability * 100).toFixed(0)} %` : "–"}
                    {s.payload.calibration && !s.payload.calibration.calibrated && (
                      <span className="ml-1 text-[10px] text-yellow-400">unkalibriert</span>
                    )}
                  </div>
                </div>
                <div title={s.payload.sizing?.steps ?? ""}>
                  <div className="text-[10px] uppercase text-gray-500">Positionsgröße</div>
                  <div className="tabular-nums">
                    {fmt(s.payload.sizing?.final_pct ?? null, 2)} %
                    <span className="ml-1 cursor-help text-[10px] text-gray-500">ⓘ Herleitung</span>
                  </div>
                </div>
              </div>

              {s.payload.why && (
                <details className="mt-3">
                  <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-300">
                    Why this signal?
                  </summary>
                  <ul className="mt-2 space-y-1 pl-4 text-xs text-gray-400">
                    {s.payload.why.map((w, i) => (
                      <li key={i} className="list-disc">{w}</li>
                    ))}
                    {s.payload.sizing?.steps && (
                      <li className="list-disc text-gray-500">{s.payload.sizing.steps}</li>
                    )}
                  </ul>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
