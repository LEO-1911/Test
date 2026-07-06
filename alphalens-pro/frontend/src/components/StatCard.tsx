// Kennzahlen-Karte mit Pflicht-Tooltip (Quelle + as_of) — Terminal-Disziplin.
export default function StatCard({
  label,
  value,
  sub,
  tooltip,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tooltip: string;
  tone?: "neutral" | "gain" | "loss" | "accent";
}) {
  const toneClass = {
    neutral: "text-gray-100",
    gain: "text-gain",
    loss: "text-loss",
    accent: "text-accent",
  }[tone];
  return (
    <div
      title={tooltip}
      className="rounded-lg border border-line bg-panel px-4 py-3 transition-colors hover:border-gray-600"
    >
      <div className="text-[10px] font-medium uppercase tracking-wider text-gray-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${toneClass}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-gray-500">{sub}</div>}
    </div>
  );
}
