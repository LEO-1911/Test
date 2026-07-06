import { useEffect, useState } from "react";

type Health = {
  status: string;
  instruments: number;
  price_bars: number;
  last_fetch_success: string | null;
  stale: boolean;
  disclaimer: string;
};

const NAV_ITEMS = [
  { id: "brief", label: "Daily Brief", milestone: "MS11" },
  { id: "picker", label: "Stock Picker", milestone: "MS5" },
  { id: "signals", label: "Signale", milestone: "MS5" },
  { id: "screener", label: "Screener", milestone: "MS4" },
  { id: "markets", label: "Märkte", milestone: "MS4" },
  { id: "whales", label: "Whales", milestone: "MS9" },
  { id: "earnings", label: "Earnings", milestone: "MS8" },
  { id: "backtest", label: "Backtest", milestone: "MS6" },
  { id: "paper", label: "Paper-Portfolio", milestone: "MS7" },
  { id: "track", label: "Track Record", milestone: "MS3" },
  { id: "chat", label: "Chat-Agent", milestone: "MS10" },
  { id: "settings", label: "Einstellungen", milestone: "MS4" },
];

function HealthBadge({ health, error }: { health: Health | null; error: boolean }) {
  if (error) {
    return (
      <span className="rounded-full bg-loss/15 px-3 py-1 text-xs font-medium text-loss">
        Backend nicht erreichbar
      </span>
    );
  }
  if (!health) {
    return <span className="text-xs text-gray-500">verbinde…</span>;
  }
  const tooltip = `Quelle: /api/health · letzter Fetch: ${health.last_fetch_success ?? "nie"}`;
  return (
    <span
      title={tooltip}
      className={`rounded-full px-3 py-1 text-xs font-medium ${
        health.stale ? "bg-yellow-500/15 text-yellow-400" : "bg-gain/15 text-gain"
      }`}
    >
      {health.stale ? "Daten veraltet" : "Daten aktuell"} · {health.instruments} Instrumente ·{" "}
      {health.price_bars.toLocaleString("de-DE")} Bars
    </span>
  );
}

export default function App() {
  const [active, setActive] = useState("markets");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);

  useEffect(() => {
    const load = () =>
      fetch("/api/health")
        .then((r) => r.json())
        .then((data: Health) => {
          setHealth(data);
          setHealthError(false);
        })
        .catch(() => setHealthError(true));
    load();
    const timer = setInterval(load, 30_000);
    return () => clearInterval(timer);
  }, []);

  const current = NAV_ITEMS.find((n) => n.id === active)!;

  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r border-line bg-panel">
        <div className="px-5 py-5">
          <div className="text-lg font-semibold tracking-tight">
            Alpha<span className="text-accent">Lens</span> Pro
          </div>
          <div className="mt-0.5 text-[11px] text-gray-500">ehrlich · erklärbar · lokal</div>
        </div>
        <nav className="flex-1 space-y-0.5 px-2">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActive(item.id)}
              className={`w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
                active === item.id
                  ? "bg-panel-hover text-accent"
                  : "text-gray-400 hover:bg-panel-hover hover:text-gray-200"
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="border-t border-line px-5 py-3 text-[10px] leading-relaxed text-gray-600">
          Keine Anlageberatung. Analyse- und Paper-Trading-Tool — es werden niemals echte Orders
          ausgeführt.
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line px-8 py-4">
          <h1 className="text-base font-semibold">{current.label}</h1>
          <HealthBadge health={health} error={healthError} />
        </header>
        <div className="flex-1 overflow-auto p-8">
          <div className="rounded-xl border border-line bg-panel p-8">
            <p className="text-sm text-gray-400">
              Diese Seite entsteht in Meilenstein{" "}
              <span className="font-mono text-accent">{current.milestone}</span> — siehe{" "}
              <span className="font-mono">IMPLEMENTATION_PLAN.md</span>. Das Grundgerüst
              (Datenpipeline, Point-in-Time-Speicher, API) läuft bereits: der Status-Badge oben
              rechts kommt live aus <span className="font-mono">/api/health</span>.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
