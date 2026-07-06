// Kurschart auf Basis von lightweight-charts (TradingView OSS), Dark-Theme.
import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type UTCTimestamp } from "lightweight-charts";
import type { PriceBar } from "../lib/api";

export default function PriceChart({ bars }: { bars: PriceBar[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const chart = createChart(el, {
      height: 320,
      layout: { background: { color: "transparent" }, textColor: "#9ca3af", fontSize: 11 },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      rightPriceScale: { borderColor: "#1f2937" },
      timeScale: { borderColor: "#1f2937" },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;
    const series = chart.addAreaSeries({
      lineColor: "#38bdf8",
      lineWidth: 2,
      topColor: "rgba(56, 189, 248, 0.25)",
      bottomColor: "rgba(56, 189, 248, 0.0)",
    });
    series.setData(
      bars
        .filter((b) => b.close !== null)
        .map((b) => ({
          time: (new Date(b.date).getTime() / 1000) as UTCTimestamp,
          value: b.close as number,
        })),
    );
    chart.timeScale().fitContent();

    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: el.clientWidth });
    });
    observer.observe(el);
    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [bars]);

  return <div ref={containerRef} className="w-full" />;
}
