/** A labeled, zoned bar with a marker at the current value — the same pattern
 * as a BMI/health-score gauge: at a glance you see not just the number, but
 * which band it falls in and how close it is to the next one. */
export function ZoneGauge({
  percent,
  zoneLabels,
  color,
}: {
  percent: number;
  /** Left-to-right zone names spanning 0–100, shown beneath the bar. */
  zoneLabels: string[];
  color: string;
}) {
  const clamped = Math.max(0, Math.min(100, percent));
  return (
    <div>
      <div className="relative h-2.5 w-full rounded-full" style={{ background: "var(--gridline)" }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${clamped}%`, background: color }}
        />
        <div
          className="absolute top-1/2 h-4 w-1.5 -translate-y-1/2 rounded-full border-2 border-white shadow"
          style={{ left: `calc(${clamped}% - 3px)`, background: color }}
        />
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
        {zoneLabels.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
    </div>
  );
}
