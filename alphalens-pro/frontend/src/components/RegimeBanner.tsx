// Regime-Gate-Banner: Zustand, Drossel-Faktor und alle Kriterien mit Begründung.
import { useEffect, useState } from "react";

export type Regime = {
  date: string;
  regime: string;
  factor: number;
  breaches: number;
  data_complete: boolean;
  criteria: { name: string; breach: boolean; evaluable: boolean; detail: string }[];
};

const REGIME_META: Record<string, { label: string; cls: string }> = {
  risk_on: { label: "Risk-on", cls: "bg-gain/15 text-gain border-gain/40" },
  neutral: { label: "Neutral", cls: "bg-yellow-500/15 text-yellow-400 border-yellow-500/40" },
  risk_off: { label: "Risk-off", cls: "bg-loss/15 text-loss border-loss/40" },
};

export default function RegimeBanner() {
  const [regime, setRegime] = useState<Regime | null>(null);

  useEffect(() => {
    fetch("/api/regime")
      .then((r) => r.json())
      .then(setRegime)
      .catch(() => setRegime(null));
  }, []);

  if (!regime) return null;
  const meta = REGIME_META[regime.regime] ?? REGIME_META.neutral;

  return (
    <div className={`rounded-lg border p-4 ${meta.cls.split(" ").pop()}  border-line bg-panel`}>
      <div className="flex items-center gap-3">
        <span className={`rounded-full border px-3 py-1 text-sm font-semibold ${meta.cls}`}>
          {meta.label}
        </span>
        <span className="text-sm text-gray-400">
          Long-Positionsgrößen x <span className="font-semibold tabular-nums">{regime.factor}</span>
          {regime.regime !== "risk_on" && " (gedrosselt, nicht versteckt)"}
        </span>
        {!regime.data_complete && (
          <span className="ml-auto text-xs text-yellow-400"
                title="Nicht bewertbare Kriterien zählen nicht als gerissen — kein stilles Raten.">
            ⚠ unvollständige Marktdaten
          </span>
        )}
      </div>
      <ul className="mt-3 space-y-1">
        {regime.criteria.map((c) => (
          <li key={c.name} className="flex items-start gap-2 text-xs">
            <span className={c.evaluable ? (c.breach ? "text-loss" : "text-gain") : "text-gray-600"}>
              {c.evaluable ? (c.breach ? "✗" : "✓") : "·"}
            </span>
            <span className={c.evaluable ? "text-gray-400" : "text-gray-600"}>{c.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
