// Screener: Filter-Engine auf der lokalen DB, sortierbare Tabelle.
// (Der KI-Screener in MS10 übersetzt Freitext in genau diese Filter.)
import { useEffect, useMemo, useState } from "react";
import { api, fmt, type ScreenerRow } from "../lib/api";
import ScoreBar from "../components/ScoreBar";

type SortKey = keyof Pick<
  ScreenerRow,
  "ticker" | "composite" | "value" | "quality" | "momentum" | "growth" | "risk_score" | "pe_ttm"
>;

export default function ScreenerPage({ onSelect }: { onSelect: (ticker: string) => void }) {
  const [rows, setRows] = useState<ScreenerRow[]>([]);
  const [q, setQ] = useState("");
  const [assetType, setAssetType] = useState("");
  const [minScore, setMinScore] = useState("");
  const [maxPe, setMaxPe] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("composite");
  const [sortDesc, setSortDesc] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (assetType) params.set("asset_type", assetType);
    if (minScore) params.set("min_score", minScore);
    if (maxPe) params.set("max_pe", maxPe);
    const timer = setTimeout(() => {
      api.screener(params).then(setRows).catch((e: Error) => setError(e.message));
    }, 250);
    return () => clearTimeout(timer);
  }, [q, assetType, minScore, maxPe]);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      const diff = typeof av === "string" ? av.localeCompare(String(bv)) : Number(av) - Number(bv);
      return sortDesc ? -diff : diff;
    });
    return copy;
  }, [rows, sortKey, sortDesc]);

  const header = (key: SortKey, label: string) => (
    <th
      className="cursor-pointer select-none px-4 py-2.5 hover:text-gray-300"
      onClick={() => {
        if (sortKey === key) setSortDesc(!sortDesc);
        else {
          setSortKey(key);
          setSortDesc(true);
        }
      }}
    >
      {label} {sortKey === key ? (sortDesc ? "↓" : "↑") : ""}
    </th>
  );

  const inputClass =
    "rounded-md border border-line bg-surface px-3 py-1.5 text-sm outline-none " +
    "placeholder:text-gray-600 focus:border-accent";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ticker oder Name…"
          className={`${inputClass} w-52`}
        />
        <select
          value={assetType}
          onChange={(e) => setAssetType(e.target.value)}
          className={inputClass}
        >
          <option value="">Alle Typen</option>
          <option value="stock">Aktien</option>
          <option value="etf">ETFs</option>
          <option value="crypto">Krypto</option>
        </select>
        <input
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
          placeholder="min. Score"
          type="number"
          className={`${inputClass} w-28`}
        />
        <input
          value={maxPe}
          onChange={(e) => setMaxPe(e.target.value)}
          placeholder="max. P/E"
          type="number"
          className={`${inputClass} w-28`}
        />
        <span className="ml-auto text-xs text-gray-500">{sorted.length} Treffer</span>
      </div>

      {error && <div className="text-sm text-loss">{error}</div>}
      <div className="overflow-x-auto rounded-lg border border-line bg-panel">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-[10px] uppercase tracking-wider text-gray-500">
              {header("ticker", "Ticker")}
              <th className="px-4 py-2.5">Name</th>
              <th className="px-4 py-2.5">Typ</th>
              {header("composite", "Score")}
              {header("value", "V")}
              {header("quality", "Q")}
              {header("momentum", "M")}
              {header("growth", "G")}
              {header("risk_score", "Risiko")}
              {header("pe_ttm", "P/E")}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={row.ticker}
                onClick={() => onSelect(row.ticker)}
                className="cursor-pointer border-b border-line/50 transition-colors last:border-0 hover:bg-panel-hover"
              >
                <td className="px-4 py-2 font-medium text-accent">{row.ticker}</td>
                <td className="max-w-56 truncate px-4 py-2 text-gray-400" title={row.name}>
                  {row.name}
                </td>
                <td className="px-4 py-2 text-xs text-gray-500">{row.asset_type}</td>
                <td className="px-4 py-2 font-semibold tabular-nums">{fmt(row.composite, 1)}</td>
                <td className="px-4 py-2"><ScoreBar score={row.value} /></td>
                <td className="px-4 py-2"><ScoreBar score={row.quality} /></td>
                <td className="px-4 py-2"><ScoreBar score={row.momentum} /></td>
                <td className="px-4 py-2"><ScoreBar score={row.growth} /></td>
                <td className="px-4 py-2 tabular-nums">
                  {row.risk_score !== null ? `${fmt(row.risk_score, 1)}/10` : "–"}
                </td>
                <td className="px-4 py-2 tabular-nums">{fmt(row.pe_ttm, 1)}</td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-sm text-gray-500">
                  Keine Treffer — Filter lockern oder erst Daten laden
                  (<span className="font-mono">make update</span>).
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
