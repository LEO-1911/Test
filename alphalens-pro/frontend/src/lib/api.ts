// Typisierte API-Zugriffe. Jede fachliche Zahl kommt mit Quelle/as_of vom Backend.

export type Health = {
  status: string;
  instruments: number;
  price_bars: number;
  last_fetch_success: string | null;
  stale: boolean;
  disclaimer: string;
};

export type MarketMetric = {
  metric: string;
  value: number | null;
  date: string;
  as_of: string;
};

export type ScreenerRow = {
  ticker: string;
  name: string;
  sector: string;
  asset_type: string;
  currency: string;
  composite: number | null;
  risk_score: number | null;
  value: number | null;
  quality: number | null;
  momentum: number | null;
  growth: number | null;
  pe_ttm: number | null;
  score_date: string | null;
};

export type ComponentScore = {
  name: string;
  score: number;
  raw_value: number | null;
  weight: number | null;
  missing: boolean;
  detail: string;
  as_of: string;
};

export type Pillar = ComponentScore & { components: ComponentScore[] };

export type Breakdown = {
  ticker: string;
  date: string;
  composite: number | null;
  risk_score: number | null;
  risk_detail: string;
  pillars: Pillar[];
};

export type PriceBar = {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
};

export type InstrumentDetail = {
  ticker: string;
  name: string;
  currency: string;
  sector: string;
  asset_type: string;
  fundamentals: {
    metric: string;
    value: number | null;
    period: string;
    as_of: string;
    source: string;
  }[];
};

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.json() as Promise<T>;
}

export const api = {
  health: () => get<Health>("/api/health"),
  marketState: () => get<MarketMetric[]>("/api/market/state"),
  scores: (limit = 100) => get<ScreenerRow[]>(`/api/scores?limit=${limit}`),
  screener: (params: URLSearchParams) => get<ScreenerRow[]>(`/api/screener?${params}`),
  breakdown: (ticker: string) =>
    get<Breakdown>(`/api/instruments/${encodeURIComponent(ticker)}/score`),
  prices: (ticker: string, days = 730) =>
    get<PriceBar[]>(`/api/instruments/${encodeURIComponent(ticker)}/prices?days=${days}`),
  instrument: (ticker: string) =>
    get<InstrumentDetail>(`/api/instruments/${encodeURIComponent(ticker)}`),
};

export function fmt(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${fmt(value / 1e12, 2)} Bio.`;
  if (abs >= 1e9) return `${fmt(value / 1e9, 2)} Mrd.`;
  if (abs >= 1e6) return `${fmt(value / 1e6, 1)} Mio.`;
  return fmt(value, 2);
}

export function asOfTooltip(source: string, asOf: string): string {
  return `Quelle: ${source} · as_of: ${asOf.replace("T", " ").slice(0, 16)}`;
}
