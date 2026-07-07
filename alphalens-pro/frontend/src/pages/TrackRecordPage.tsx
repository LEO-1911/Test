// Track Record — das Herzstück der Glaubwürdigkeit (USP 3 + 5):
// Hash-Chain-Status, ECHTE Trefferquoten je Signaltyp (auch wenn sie schlecht
// sind), Brier-Score, Kalibrierungs-Badges und das komplette Ledger.
import { useEffect, useState } from "react";
import {
  api,
  fmt,
  type ChainStatus,
  type LedgerEntryView,
  type ReliabilityData,
  type SignalTypeStats,
} from "../lib/api";
import StatCard from "../components/StatCard";

function ReliabilityChart({ data }: { data: ReliabilityData }) {
  // Reliability-Diagramm als schlichtes SVG: Diagonale = perfekte Kalibrierung.
  const size = 220;
  const pad = 28;
  const scale = (v: number) => pad + v * (size - 2 * pad);
  return (
    <svg width={size} height={size} className="shrink-0">
      <line x1={scale(0)} y1={size - scale(0)} x2={scale(1)} y2={size - scale(1)}
            stroke="#374151" strokeDasharray="4 3" />
      {[0, 0.5, 1].map((t) => (
        <g key={t}>
          <text x={scale(t)} y={size - 8} fill="#6b7280" fontSize={9} textAnchor="middle">
            {t}
          </text>
          <text x={12} y={size - scale(t) + 3} fill="#6b7280" fontSize={9} textAnchor="middle">
            {t}
          </text>
        </g>
      ))}
      {data.bins.map((b) => (
        <circle
          key={b.bin_low}
          cx={scale(b.mean_predicted)}
          cy={size - scale(b.observed_rate)}
          r={Math.min(10, 3 + Math.sqrt(b.count))}
          fill="#38bdf8"
          fillOpacity={0.75}
        >
          <title>
            {`Prognose Ø ${(b.mean_predicted * 100).toFixed(0)} % → beobachtet ${(b.observed_rate * 100).toFixed(0)} % (n=${b.count})`}
          </title>
        </circle>
      ))}
      <text x={size / 2} y={12} fill="#9ca3af" fontSize={10} textAnchor="middle">
        prognostiziert → beobachtet
      </text>
    </svg>
  );
}

export default function TrackRecordPage() {
  const [chain, setChain] = useState<ChainStatus | null>(null);
  const [stats, setStats] = useState<SignalTypeStats[]>([]);
  const [entries, setEntries] = useState<LedgerEntryView[]>([]);
  const [reliability, setReliability] = useState<ReliabilityData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.ledgerStats()
      .then((d) => {
        setChain(d.chain);
        setStats(d.by_signal_type);
      })
      .catch((e: Error) => setError(e.message));
    api.ledgerEntries(100).then(setEntries).catch(() => {});
    api.ledgerReliability().then(setReliability).catch(() => {});
  }, []);

  const totalSignals = stats.reduce((a, s) => a + s.n_signals, 0);
  const totalClosed = stats.reduce((a, s) => a + s.n_closed, 0);

  return (
    <div className="space-y-6">
      {error && <div className="text-sm text-loss">{error}</div>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard
          label="Ledger-Integrität"
          value={chain ? (chain.valid ? "✓ intakt" : "✗ GEBROCHEN") : "…"}
          sub={chain?.valid === false ? `ab Eintrag #${chain.first_broken_id}` : "Hash-Chain nachgerechnet"}
          tooltip="Quelle: /api/ledger/verify — SHA-256-Kette wird bei jedem Aufruf komplett neu berechnet"
          tone={chain ? (chain.valid ? "gain" : "loss") : "neutral"}
        />
        <StatCard
          label="Ledger-Einträge"
          value={chain ? String(chain.entries) : "…"}
          sub="append-only, unveränderbar"
          tooltip="Jeder Eintrag ist kryptographisch mit dem vorherigen verkettet"
        />
        <StatCard
          label="Signale / Picks"
          value={String(totalSignals)}
          sub={`${totalClosed} abgeschlossen`}
          tooltip="Quelle: /api/ledger/stats"
        />
        <StatCard
          label="Brier-Score (alle)"
          value={reliability?.brier != null ? fmt(reliability.brier, 3) : "–"}
          sub="0 = perfekt · 0,25 = uninformiert"
          tooltip={`über ${reliability?.n ?? 0} Prognosen mit Ausgang`}
          tone="accent"
        />
      </div>

      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
          Trefferquote je Signaltyp — ehrlich, inklusive Kalibrierungsstatus
        </h2>
        {stats.length === 0 ? (
          <div className="rounded-lg border border-line bg-panel p-5 text-sm text-gray-400">
            Noch keine Signale im Ledger. Die Signal-Engine und der Stock Picker (MS5)
            schreiben ab ihrem ersten Lauf jeden Vorschlag hierher — mit Zeitstempel,
            Preis und Wahrscheinlichkeit, unlöschbar. Diese Seite zeigt dann die echte
            Historie, auch wenn sie unbequem ist.
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-line bg-panel">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[10px] uppercase tracking-wider text-gray-500">
                  <th className="px-4 py-2.5">Signaltyp</th>
                  <th className="px-4 py-2.5">Signale</th>
                  <th className="px-4 py-2.5">geschlossen</th>
                  <th className="px-4 py-2.5" title="roh / Laplace-geglättet">Hit-Rate</th>
                  <th className="px-4 py-2.5">Ø-Rendite</th>
                  <th className="px-4 py-2.5" title="0 = perfekt, 0,25 = uninformiert">Brier</th>
                  <th className="px-4 py-2.5">Kalibrierung</th>
                </tr>
              </thead>
              <tbody>
                {stats.map((s) => (
                  <tr key={s.signal_type} className="border-b border-line/50 last:border-0">
                    <td className="px-4 py-2 font-mono text-xs text-accent">{s.signal_type}</td>
                    <td className="px-4 py-2 tabular-nums">{s.n_signals}</td>
                    <td className="px-4 py-2 tabular-nums">{s.n_closed}</td>
                    <td className="px-4 py-2 tabular-nums">
                      {s.hit_rate !== null ? `${(s.hit_rate * 100).toFixed(0)} %` : "–"}
                      <span className="text-xs text-gray-500">
                        {" "}/ {(s.hit_rate_laplace * 100).toFixed(0)} %
                      </span>
                    </td>
                    <td className={`px-4 py-2 tabular-nums ${
                      (s.avg_return_pct ?? 0) >= 0 ? "text-gain" : "text-loss"}`}>
                      {s.avg_return_pct !== null ? `${fmt(s.avg_return_pct, 2)} %` : "–"}
                    </td>
                    <td className="px-4 py-2 tabular-nums">{fmt(s.brier, 3)}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] ${
                        s.calibration.calibrated
                          ? "bg-gain/15 text-gain"
                          : "bg-yellow-500/15 text-yellow-400"
                      }`}>
                        {s.calibration.label}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {reliability && reliability.n > 0 && (
        <section className="flex items-start gap-6 rounded-lg border border-line bg-panel p-5">
          <ReliabilityChart data={reliability} />
          <div className="text-sm text-gray-400">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
              Reliability-Diagramm
            </div>
            Punkte auf der Diagonale = perfekt kalibrierte Wahrscheinlichkeiten. Punkte
            darüber: wir waren zu pessimistisch, darunter: zu optimistisch. Basis:{" "}
            {reliability.n} abgeschlossene Prognosen.
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
          Ledger (neueste zuerst)
        </h2>
        <div className="overflow-x-auto rounded-lg border border-line bg-panel">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-line text-left text-[10px] uppercase tracking-wider text-gray-500">
                <th className="px-4 py-2.5">#</th>
                <th className="px-4 py-2.5">Zeit (UTC)</th>
                <th className="px-4 py-2.5">Typ</th>
                <th className="px-4 py-2.5">Ticker</th>
                <th className="px-4 py-2.5">Preis</th>
                <th className="px-4 py-2.5">P(Erfolg)</th>
                <th className="px-4 py-2.5">Ausgang</th>
                <th className="px-4 py-2.5">Hash</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => {
                const result = e.entry_type === "outcome"
                  ? String(e.payload.result ?? "")
                  : e.outcome
                    ? `${String(e.outcome.result)} (${fmt(Number(e.outcome.return_pct), 2)} %)`
                    : e.entry_type === "signal" || e.entry_type === "pick"
                      ? "offen"
                      : "";
                return (
                  <tr key={e.id} className="border-b border-line/40 last:border-0">
                    <td className="px-4 py-2 tabular-nums text-gray-500">{e.id}</td>
                    <td className="px-4 py-2 font-mono text-xs text-gray-400">
                      {e.ts_utc.replace("T", " ").slice(0, 16)}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${
                        e.entry_type === "outcome"
                          ? "bg-panel-hover text-gray-400"
                          : "bg-accent/15 text-accent"
                      }`}>
                        {e.entry_type}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-medium">{e.ticker}</td>
                    <td className="px-4 py-2 tabular-nums">{fmt(e.price_at_creation, 2)}</td>
                    <td className="px-4 py-2 tabular-nums">
                      {e.probability !== null ? `${(e.probability * 100).toFixed(0)} %` : "–"}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-400">{result}</td>
                    <td className="px-4 py-2 font-mono text-[10px] text-gray-600" title={e.entry_hash}>
                      {e.entry_hash.slice(0, 12)}…
                    </td>
                  </tr>
                );
              })}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-sm text-gray-500">
                    Ledger ist leer — der erste Eintrag entsteht mit dem ersten Signal (MS5).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
