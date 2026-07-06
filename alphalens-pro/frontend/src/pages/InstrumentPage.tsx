// Instrument-Detail: Kurschart + "Why this score?"-Panel (USP 2) + Fundamentals.
// Jede Zahl trägt Quelle und as_of im Tooltip.
import { useEffect, useState } from "react";
import {
  api,
  asOfTooltip,
  fmt,
  fmtCompact,
  type Breakdown,
  type InstrumentDetail,
  type PriceBar,
} from "../lib/api";
import PriceChart from "../components/PriceChart";
import ScoreBar from "../components/ScoreBar";

const PILLAR_LABELS: Record<string, string> = {
  value: "Value",
  quality: "Quality",
  momentum: "Momentum",
  growth: "Growth",
};

function riskTone(risk: number | null): string {
  if (risk === null) return "text-gray-400";
  if (risk <= 3.5) return "text-gain";
  if (risk <= 6.5) return "text-yellow-400";
  return "text-loss";
}

export default function InstrumentPage({
  ticker,
  onBack,
}: {
  ticker: string;
  onBack: () => void;
}) {
  const [detail, setDetail] = useState<InstrumentDetail | null>(null);
  const [bars, setBars] = useState<PriceBar[]>([]);
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [open, setOpen] = useState<string | null>("momentum");

  useEffect(() => {
    api.instrument(ticker).then(setDetail).catch(() => setDetail(null));
    api.prices(ticker).then(setBars).catch(() => setBars([]));
    api.breakdown(ticker).then(setBreakdown).catch(() => setBreakdown(null));
  }, [ticker]);

  const lastBar = bars.length ? bars[bars.length - 1] : null;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-4">
        <button
          onClick={onBack}
          className="rounded-md border border-line px-3 py-1.5 text-xs text-gray-400 hover:border-accent hover:text-accent"
        >
          ← zurück
        </button>
        <div>
          <div className="flex items-baseline gap-3">
            <h2 className="text-xl font-semibold">{ticker}</h2>
            <span className="text-sm text-gray-400">{detail?.name}</span>
            <span className="rounded bg-panel-hover px-1.5 py-0.5 text-[10px] uppercase text-gray-400">
              {detail?.asset_type}
            </span>
          </div>
          <div className="text-xs text-gray-500">
            {detail?.sector || "—"} · {detail?.currency}
          </div>
        </div>
        {lastBar && (
          <div className="ml-auto text-right" title={`Quelle: Kursdatenbank · Schluss ${lastBar.date}`}>
            <div className="text-2xl font-semibold tabular-nums">
              {fmt(lastBar.close, 2)}{" "}
              <span className="text-sm text-gray-500">{detail?.currency}</span>
            </div>
            <div className="text-xs text-gray-500">Schluss {lastBar.date}</div>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-line bg-panel p-4">
        {bars.length ? (
          <PriceChart bars={bars} />
        ) : (
          <div className="py-16 text-center text-sm text-gray-500">keine Kursdaten</div>
        )}
      </div>

      {breakdown && (
        <section className="rounded-lg border border-line bg-panel">
          <div className="flex items-center gap-8 border-b border-line px-5 py-4">
            <div title={`Scoring-Stichtag: ${breakdown.date} · Gewichte: config/scoring.yaml`}>
              <div className="text-[10px] uppercase tracking-wider text-gray-500">
                Composite Score
              </div>
              <div className="text-3xl font-semibold tabular-nums">
                {breakdown.composite !== null ? fmt(breakdown.composite, 1) : "–"}
                <span className="text-sm text-gray-500"> / 100</span>
              </div>
            </div>
            <div title={breakdown.risk_detail}>
              <div className="text-[10px] uppercase tracking-wider text-gray-500">Risiko</div>
              <div className={`text-3xl font-semibold tabular-nums ${riskTone(breakdown.risk_score)}`}>
                {fmt(breakdown.risk_score, 1)}
                <span className="text-sm text-gray-500"> / 10</span>
              </div>
            </div>
            <div className="ml-auto max-w-md text-right text-[11px] leading-snug text-gray-500">
              „Why this score?" — jede Komponente zeigt Rohwert, Gewicht und Herkunft.
              Fehlende Daten werden neutral (50) gewertet und als{" "}
              <span className="text-yellow-400">fehlend</span> markiert, nie versteckt.
            </div>
          </div>
          {breakdown.pillars.map((pillar) => (
            <div key={pillar.name} className="border-b border-line/50 last:border-0">
              <button
                onClick={() => setOpen(open === pillar.name ? null : pillar.name)}
                className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-panel-hover"
              >
                <span className="w-24 text-sm font-medium">
                  {PILLAR_LABELS[pillar.name] ?? pillar.name}
                </span>
                <span className="text-xs text-gray-500">
                  Gewicht {((pillar.weight ?? 0) * 100).toFixed(0)} %
                </span>
                <div className="ml-auto flex items-center gap-3">
                  {pillar.missing && (
                    <span className="text-[10px] text-yellow-400">alle Komponenten fehlend</span>
                  )}
                  <ScoreBar score={pillar.score} missing={pillar.missing} />
                  <span className="text-gray-600">{open === pillar.name ? "▾" : "▸"}</span>
                </div>
              </button>
              {open === pillar.name && (
                <table className="w-full text-[13px]">
                  <tbody>
                    {pillar.components.map((c) => (
                      <tr key={c.name} className="border-t border-line/40">
                        <td className="py-2 pl-10 pr-4 font-mono text-xs text-gray-400">
                          {c.name.split(".")[1]}
                        </td>
                        <td className="px-3 py-2">
                          <ScoreBar score={c.score} missing={c.missing} />
                        </td>
                        <td
                          className="px-3 py-2 text-xs tabular-nums text-gray-500"
                          title="effektives Gewicht innerhalb der Säule (renormalisiert)"
                        >
                          w={((c.weight ?? 0) * 100).toFixed(0)} %
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-400" title={asOfTooltip("Scoring-Engine", c.as_of)}>
                          {c.missing && <span className="mr-1 text-yellow-400">⚠</span>}
                          {c.detail}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </section>
      )}

      {detail && detail.fundamentals.length > 0 && (
        <section className="rounded-lg border border-line bg-panel">
          <div className="border-b border-line px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
            Fundamentals (jüngster Stand je Metrik)
          </div>
          <table className="w-full text-sm">
            <tbody>
              {detail.fundamentals.map((f) => (
                <tr key={f.metric} className="border-b border-line/40 last:border-0">
                  <td className="px-5 py-2 font-mono text-xs text-gray-400">{f.metric}</td>
                  <td className="px-5 py-2 text-right tabular-nums">{fmtCompact(f.value)}</td>
                  <td className="px-5 py-2 text-right text-xs text-gray-600" title={asOfTooltip(f.source, f.as_of)}>
                    {f.source} · as_of {f.as_of.slice(0, 10)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
