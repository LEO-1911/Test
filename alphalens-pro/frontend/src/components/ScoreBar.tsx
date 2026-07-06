// Kompakter 0-100-Balken mit Signalfarbe. Für Tabellenzellen und das Why-Panel.
export default function ScoreBar({
  score,
  missing = false,
}: {
  score: number | null;
  missing?: boolean;
}) {
  if (score === null) return <span className="text-gray-600">–</span>;
  const color = missing
    ? "bg-gray-600"
    : score >= 60
      ? "bg-gain"
      : score >= 40
        ? "bg-accent"
        : "bg-loss";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-line">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(100, score)}%` }} />
      </div>
      <span className={`w-9 text-right tabular-nums ${missing ? "text-gray-500" : ""}`}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}
