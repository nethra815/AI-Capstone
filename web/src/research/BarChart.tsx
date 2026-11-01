interface Row {
  label: string;
  value: number | null; // 0..1
  display: string;
}

/** Small horizontal bar chart for 0..1 metrics. Plain divs, no chart library. */
export function BarChart({ title, note, rows }: { title: string; note: string; rows: Row[] }) {
  return (
    <figure>
      <figcaption className="mb-2 flex items-baseline justify-between gap-2">
        <span className="text-ui font-medium text-ink">{title}</span>
        <span className="text-label text-ink-3">{note}</span>
      </figcaption>
      <dl className="space-y-1.5">
        {rows.map((r) => (
          <div key={r.label} className="grid grid-cols-[8.5rem_1fr_3.5rem] items-center gap-3">
            <dt className="truncate text-small text-ink-2">{r.label}</dt>
            <dd className="h-2.5 bg-rule/50" aria-hidden>
              <div className="h-full bg-accent" style={{ width: `${Math.max(0, Math.min(1, r.value ?? 0)) * 100}%` }} />
            </dd>
            <dd className="text-right font-mono text-mono tabular-nums text-ink">{r.display}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}
