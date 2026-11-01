import type { AskResult } from "../api";
import { AbstainNote } from "./AbstainNote";
import { CheckDetails } from "./CheckDetails";
import { ConflictCompare } from "./ConflictCompare";
import { citedDocCount, searchedFor } from "./explain";
import { Feedback } from "./Feedback";

interface Props {
  result: AskResult;
  fixture?: boolean;
  activeClaim: number | null;
  onCite: (claimIndex: number, trigger: HTMLElement) => void;
}

function OutcomeLabel({ result }: { result: AskResult }) {
  if (result.outcome === "abstain") return <p className="label">Not enough evidence</p>;
  if (result.outcome === "conflict")
    return (
      <p className="label flex items-center gap-2 !text-changed">
        <span aria-hidden className="inline-block size-1.5 rounded-full bg-changed" />
        Policy changed
      </p>
    );
  const n = citedDocCount(result);
  return (
    <p className="label flex items-center gap-2 !text-accent">
      <span aria-hidden className="inline-block size-1.5 rounded-full bg-accent" />
      Supported by {n} {n === 1 ? "source" : "sources"}
    </p>
  );
}

export function AnswerNote({ result, fixture, activeClaim, onCite }: Props) {
  const searched = searchedFor(result);
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <OutcomeLabel result={result} />
        {fixture && (
          <span className="rounded-sm border border-rule-strong px-1.5 text-label text-ink-3">Dev fixture</span>
        )}
      </div>

      {searched && (
        <p className="text-small text-ink-3">
          Searched for: <span className="text-ink-2 italic">{searched}</span>
        </p>
      )}

      {result.outcome === "abstain" ? (
        <AbstainNote result={result} />
      ) : (
        <p className="font-serif text-answer text-ink">
          {result.claims.map((c, i) => (
            <span key={i}>
              {c.text}
              <sup className="ml-px">
                <button
                  type="button"
                  onClick={(e) => onCite(i, e.currentTarget)}
                  aria-label={`Source ${i + 1}`}
                  aria-pressed={activeClaim === i}
                  className={`rounded-sm px-1 py-0.5 font-sans text-[11px] leading-none font-semibold transition-colors duration-150 ${
                    activeClaim === i ? "bg-accent text-white" : "text-accent hover:bg-accent-tint"
                  }`}
                >
                  {i + 1}
                </button>
              </sup>{" "}
            </span>
          ))}
        </p>
      )}

      {result.outcome === "conflict" && result.conflicts.length > 0 && (
        <ConflictCompare conflicts={result.conflicts} asOf={result.as_of} />
      )}

      {result.notices.length > 0 && (
        <ul className="space-y-1.5 border-l-2 border-rule pl-3">
          {result.notices.map((n) => (
            <li key={n} className="text-small text-ink-2">
              <span className="font-medium text-ink-3">Note. </span>
              {n}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-x-6 gap-y-3 border-t border-rule pt-3 sm:flex-row sm:items-start sm:justify-between">
        <CheckDetails result={result} />
        <Feedback question={result.question} outcome={result.outcome} />
      </div>
    </div>
  );
}
