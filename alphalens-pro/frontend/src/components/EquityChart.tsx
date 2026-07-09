// Equity-Kurve (+ optionaler Benchmark). Datumsbasierte Kurven rendern über
// lightweight-charts; Trade-Sequenzen (Signal-Backtests) als schlichtes SVG.
import { useEffect, useRef } from "react";
import { createChart, type UTCTimestamp } from "lightweight-charts";

export type EquityPoint = [string, number];

function isIsoDate(label: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(label);
}

function SvgLine({ points }: { points: EquityPoint[] }) {
  const width = 640;
  const height = 220;
  const pad = 10;
  const values = points.map(([, v]) => v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const coords = points.map(([, v], i) => {
    const x = pad + (i / Math.max(1, points.length - 1)) * (width - 2 * pad);
    const y = height - pad - ((v - min) / span) * (height - 2 * pad);
    return `${x},${y}`;
  });
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      <polyline points={coords.join(" ")} fill="none" stroke="#38bdf8" strokeWidth={1.5} />
      <text x={pad} y={12} fill="#6b7280" fontSize={10}>{max.toFixed(2)}</text>
      <text x={pad} y={height - 2} fill="#6b7280" fontSize={10}>{min.toFixed(2)}</text>
    </svg>
  );
}

export default function EquityChart({
  equity,
  benchmark,
}: {
  equity: EquityPoint[];
  benchmark?: EquityPoint[] | null;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const dateBased = equity.length > 0 && isIsoDate(equity[0][0]);

  useEffect(() => {
    const el = ref.current;
    if (!el || !dateBased) return;
    const chart = createChart(el, {
      height: 300,
      layout: { background: { color: "transparent" }, textColor: "#9ca3af", fontSize: 11 },
      grid: { vertLines: { color: "#1f2937" }, horzLines: { color: "#1f2937" } },
      rightPriceScale: { borderColor: "#1f2937" },
      timeScale: { borderColor: "#1f2937" },
    });
    const toData = (points: EquityPoint[]) =>
      points.map(([d, v]) => ({
        time: (new Date(d).getTime() / 1000) as UTCTimestamp,
        value: v,
      }));
    const strategySeries = chart.addLineSeries({ color: "#38bdf8", lineWidth: 2 });
    strategySeries.setData(toData(equity));
    if (benchmark && benchmark.length > 1) {
      const benchSeries = chart.addLineSeries({
        color: "#6b7280",
        lineWidth: 1,
        lineStyle: 1,
      });
      benchSeries.setData(toData(benchmark));
    }
    chart.timeScale().fitContent();
    const observer = new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth }));
    observer.observe(el);
    return () => {
      observer.disconnect();
      chart.remove();
    };
  }, [equity, benchmark, dateBased]);

  if (!dateBased) return <SvgLine points={equity} />;
  return (
    <div>
      <div ref={ref} className="w-full" />
      {benchmark && benchmark.length > 1 && (
        <div className="mt-1 text-[10px] text-gray-500">
          <span className="text-accent">━</span> Strategie ·{" "}
          <span className="text-gray-500">┄</span> S&P 500 (gleiches Startkapital)
        </div>
      )}
    </div>
  );
}
