import type { AskResult } from "../api";
import { friendlyAbstainReason, suggestedOffice } from "./explain";

export function AbstainNote({ result }: { result: AskResult }) {
  const office = suggestedOffice(result);
  return (
    <div className="space-y-3">
      <p className="font-serif text-answer text-ink">
        The official documents don't clearly answer this, so no answer is given rather than a guess.
      </p>
      <p className="text-ui text-ink-2">{friendlyAbstainReason(result.abstain_reason)}</p>
      <p className="text-ui text-ink-2">
        You could rephrase using the term the rules would use, or check the policy date and batch.
        {office ? (
          <>
            {" "}For a definite answer, contact the <span className="font-medium text-ink">{office}</span>.
          </>
        ) : (
          " For a definite answer, contact the relevant college office."
        )}
      </p>
    </div>
  );
}
