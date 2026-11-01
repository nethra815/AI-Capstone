import { useId, useState, type FormEvent } from "react";
import { api, ApiError, MODES, type AskResult, type Mode } from "../api";
import { clauseLabels, MODE_LABELS, seconds, todayIso } from "../lib/format";
import { useElapsed, type HealthState } from "../lib/hooks";
import { healthMessage } from "../lib/Status";
import { friendlyAbstainReason } from "../ask/explain";

type Side = { status: "idle" } | { status: "pending" } | { status: "done"; result: AskResult } | { status: "error"; message: string };

const OUTCOME_LABEL = { answer: "Answer", conflict: "Policy changed", abstain: "Not enough evidence" } as const;

function Column({ mode, side, startedAt }: { mode: Mode; side: Side; startedAt: number }) {
  const elapsed = useElapsed(startedAt, side.status === "pending");
  return (
    <div className="min-w-0 py-4 sm:px-5 sm:first:pl-0 sm:last:pr-0">
      <h3 className="label">{MODE_LABELS[mode]}</h3>
      {side.status === "idle" && <p className="mt-2 text-small text-ink-3">No question asked yet.</p>}
      {side.status === "pending" && (
        <p role="status" className="mt-2 text-small text-ink-3">
          Checking official documents… <span className="tabular-nums">{elapsed} s</span>
        </p>
      )}
      {side.status === "error" && (
        <p role="alert" className="mt-2 text-small text-changed">
          {side.message}
        </p>
      )}
      {side.status === "done" && (
        <div className="mt-2 space-y-3">
          <p className={`text-small font-medium ${side.result.outcome === "abstain" ? "text-ink-3" : side.result.outcome === "conflict" ? "text-changed" : "text-accent"}`}>
            {OUTCOME_LABEL[side.result.outcome]}
          </p>
          {side.result.outcome === "abstain" ? (
            <p className="font-serif text-[16px] leading-relaxed text-ink-2">{friendlyAbstainReason(side.result.abstain_reason)}</p>
          ) : (
            <ol className="space-y-3">
              {side.result.claims.map((c, i) => {
                const ci = c.citations[0];
                return (
                  <li key={i}>
                    <p className="font-serif text-[16px] leading-relaxed text-ink">
                      {c.text}
                      {!c.verified && <span className="ml-1 font-sans text-label text-changed">(not verified)</span>}
                    </p>
                    {ci && (
                      <p className="mt-0.5 text-label text-ink-3">
                        <span className="font-mono">{ci.doc_id}</span> · {ci.section}
                        {ci.clauses.length > 0 && <> · cl. <span className="font-mono">{clauseLabels(ci.clauses, ci.section).join(", ")}</span></>}
                      </p>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
          <p className="text-label text-ink-3">
            {side.result.n_verified ?? 0} of {side.result.n_claims ?? 0} claims verified · coverage{" "}
            {side.result.coverage == null ? "not measured" : side.result.coverage.toFixed(2)} · {seconds(side.result.latency_ms)}
          </p>
        </div>
      )}
    </div>
  );
}

export function CompareModes({ health }: { health: HealthState }) {
  const [question, setQuestion] = useState("");
  const [modes, setModes] = useState<[Mode, Mode]>(["hybrid", "evidence_aware"]);
  const [sides, setSides] = useState<[Side, Side]>([{ status: "idle" }, { status: "idle" }]);
  const [startedAt, setStartedAt] = useState(Date.now());
  const ids = [useId(), useId(), useId()];
  const notReady = healthMessage(health);
  const busy = sides.some((s) => s.status === "pending");

  const run = (e: FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || busy || notReady) return;
    setStartedAt(Date.now());
    setSides([{ status: "pending" }, { status: "pending" }]);
    modes.forEach((mode, i) => {
      api
        .ask({ question: q, mode, as_of: todayIso() })
        .then((result): Side => ({ status: "done", result }))
        .catch((err): Side => ({ status: "error", message: err instanceof ApiError ? err.message : "Something went wrong, try again." }))
        .then((s) => setSides((prev) => (i === 0 ? [s, prev[1]] : [prev[0], s])));
    });
  };

  const modeSelect = (i: 0 | 1) => (
    <label htmlFor={ids[i + 1]} className="flex items-center gap-2 text-small text-ink-2">
      {i === 0 ? "Mode A" : "Mode B"}
      <select
        id={ids[i + 1]}
        value={modes[i]}
        onChange={(e) => setModes((m) => (i === 0 ? [e.target.value as Mode, m[1]] : [m[0], e.target.value as Mode]))}
        className="field h-8 px-1.5 text-small"
      >
        {MODES.map((m) => (
          <option key={m} value={m}>
            {MODE_LABELS[m]}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <section className="mt-14" aria-labelledby="compare">
      <h2 id="compare" className="font-serif text-subhead font-semibold">Compare modes</h2>
      <p className="mt-1 max-w-[65ch] text-ui text-ink-2">
        Ask one question in two modes at once. Baseline modes skip date filtering and verification, so they may cite
        outdated rules. Uses today's date and an automatic batch.
      </p>
      <form onSubmit={run} className="mt-4 space-y-3">
        <label htmlFor={ids[0]} className="sr-only">Question to compare</label>
        <input
          id={ids[0]}
          value={question}
          maxLength={500}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What is the attendance condonation fee per course?"
          disabled={!!notReady}
          className="field h-10 w-full px-3 text-[15px] placeholder:text-ink-3"
        />
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          {modeSelect(0)}
          {modeSelect(1)}
          <button type="submit" className="btn btn-primary ml-auto" disabled={!question.trim() || busy || !!notReady}>
            {busy ? "Comparing…" : "Compare"}
          </button>
        </div>
        {notReady && <p className="text-small text-ink-3">{notReady}</p>}
      </form>
      <div className="mt-6 grid divide-y divide-rule border-y border-rule sm:grid-cols-2 sm:divide-x sm:divide-y-0">
        <Column mode={modes[0]} side={sides[0]} startedAt={startedAt} />
        <Column mode={modes[1]} side={sides[1]} startedAt={startedAt} />
      </div>
    </section>
  );
}
