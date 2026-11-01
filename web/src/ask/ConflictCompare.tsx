import type { Conflict } from "../api";
import { formatDate } from "../lib/format";

/** "newer (effective 2026-10-12) as of 2026-11-01" -> which side applies and from when. */
function parseApplies(applies: string) {
  const side = /^\s*older/i.test(applies) ? "older" : "newer";
  const eff = /effective\s+(\d{4}-\d{2}-\d{2})/.exec(applies)?.[1] ?? null;
  return { side, eff } as const;
}

interface SideProps {
  heading: string;
  source: string;
  says: string;
  applies: boolean;
  asOf: string;
  note?: string;
}

function Side({ heading, source, says, applies, asOf, note }: SideProps) {
  return (
    <div className={`px-4 py-3 ${applies ? "bg-paper-raised" : ""}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="label">{heading}</h3>
        {applies ? (
          <span className="text-label font-medium text-accent">Applies on {formatDate(asOf)}</span>
        ) : (
          <span className="text-label text-ink-3">Does not apply on {formatDate(asOf)}</span>
        )}
      </div>
      <p className="mt-1 text-small text-ink-2">{source}</p>
      {note && <p className="text-label text-ink-3">{note}</p>}
      <p className={`mt-2 font-serif text-[16px] leading-relaxed ${applies ? "text-ink" : "text-ink-3"}`}>{says}</p>
    </div>
  );
}

export function ConflictCompare({ conflicts, asOf }: { conflicts: Conflict[]; asOf: string }) {
  return (
    <section aria-label="Policy change" className="space-y-3">
      {conflicts.map((c, i) => {
        const { side, eff } = parseApplies(c.applies);
        return (
          <div
            key={i}
            className="grid divide-y divide-rule overflow-hidden rounded-md border border-rule sm:grid-cols-2 sm:divide-x sm:divide-y-0"
          >
            <Side heading="Earlier rule" source={c.older_source} says={c.older_says} applies={side === "older"} asOf={asOf} />
            <Side
              heading="Revised rule"
              source={c.newer_source}
              says={c.newer_says}
              applies={side === "newer"}
              asOf={asOf}
              note={eff ? `Effective ${formatDate(eff)}` : undefined}
            />
          </div>
        );
      })}
    </section>
  );
}
