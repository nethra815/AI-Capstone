import { RotateCcw } from "lucide-react";
import { formatDate } from "../lib/format";
import { useElapsed } from "../lib/hooks";
import { AnswerNote } from "./AnswerNote";
import type { Turn } from "./AskView";

interface Props {
  turn: Turn;
  activeClaim: number | null;
  onCite: (claimIndex: number, trigger: HTMLElement) => void;
  onRetry: () => void;
}

export function TurnView({ turn, activeClaim, onCite, onRetry }: Props) {
  const elapsed = useElapsed(turn.startedAt, turn.status === "pending");
  return (
    <article className="animate-fade-in" aria-busy={turn.status === "pending"}>
      <header className="mb-4 border-b border-rule pb-2">
        <h2 className="text-[15px] font-medium text-ink-2">{turn.question}</h2>
        <p className="mt-0.5 text-label text-ink-3">
          As of {formatDate(turn.as_of)} · Batch {turn.batch ?? "auto"}
        </p>
      </header>

      {turn.status === "pending" && (
        <p role="status" className="font-serif text-answer text-ink-3">
          Checking official documents… <span className="font-sans text-small tabular-nums">{elapsed} s</span>
        </p>
      )}

      {turn.status === "error" && turn.error && (
        <div role="alert" className="space-y-3">
          <p className="font-serif text-answer text-ink">Something went wrong, try again.</p>
          <p className="text-small text-ink-2">{turn.error.message}</p>
          {turn.error.retryable && (
            <button type="button" onClick={onRetry} className="btn btn-quiet">
              <RotateCcw size={16} aria-hidden /> Try again
            </button>
          )}
        </div>
      )}

      {turn.status === "done" && turn.result && (
        <AnswerNote
          result={turn.result}
          activeClaim={activeClaim}
          onCite={onCite}
        />
      )}
    </article>
  );
}
