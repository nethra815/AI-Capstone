import { ChevronRight } from "lucide-react";
import type { AskResult } from "../api";
import { formatDate, MODE_LABELS, seconds } from "../lib/format";
import { LANGUAGES } from "./explain";

/** Built only from fields the pipeline returned. Nothing here is simulated. */
export function CheckDetails({ result }: { result: AskResult }) {
  const rows: [string, string][] = [
    ["Passages retrieved", String(result.retrieved_ids.length)],
    ["Passages used as evidence", result.context_ids ? String(result.context_ids.length) : "Not reported in this mode"],
    ["Evidence coverage", result.coverage == null ? "Not measured in this mode" : result.coverage.toFixed(2)],
    [
      "Claims verified against sources",
      result.n_claims == null ? "None drafted" : `${result.n_verified ?? 0} of ${result.n_claims}`,
    ],
    ["Detected language", LANGUAGES[result.language] ?? result.language],
    ["Policy date and batch", `${formatDate(result.as_of)} · ${result.batch ?? "not specified"}`],
    ["Retrieval mode", MODE_LABELS[result.mode] ?? result.mode],
    ["Time taken", seconds(result.latency_ms)],
  ];
  return (
    <details className="group min-w-0 flex-1">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1 rounded-sm text-small text-ink-2 hover:text-ink [&::-webkit-details-marker]:hidden">
        <ChevronRight size={16} aria-hidden className="transition-transform duration-150 group-open:rotate-90" />
        How this answer was checked
      </summary>
      <dl className="mt-3 grid max-w-md grid-cols-[minmax(0,1fr)_auto] gap-x-6 gap-y-1.5 text-small">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-3">{k}</dt>
            <dd className="text-right tabular-nums text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 max-w-md text-label text-ink-3">
        Coverage measures how well the best passage matches the question's key terms. Low coverage means no answer is
        given.
      </p>
    </details>
  );
}
