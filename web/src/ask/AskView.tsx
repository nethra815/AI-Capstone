import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, type AskResult, type DocumentInfo } from "../api";
import { useLoad, type HealthState } from "../lib/hooks";
import { todayIso } from "../lib/format";
import { Composer, type PolicyContextValue } from "./Composer";
import { EmptyState } from "./EmptyState";
import { SourcePanel } from "./SourcePanel";
import { TurnView } from "./Turn";

export interface Turn {
  id: number;
  question: string;
  as_of: string;
  batch: string | null;
  startedAt: number;
  status: "pending" | "done" | "error";
  result?: AskResult;
  error?: ApiError;
}

/** Which footnote is open in the source panel. */
export interface OpenSource {
  turnId: number;
  claimIndex: number;
  trigger: HTMLElement | null;
}

let nextId = 1;

export function AskView({ health }: { health: HealthState }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [context, setContext] = useState<PolicyContextValue>({ as_of: todayIso(), batch: "auto" });
  const [open, setOpen] = useState<OpenSource | null>(null);
  const ready = health.status === "ready";
  const docs = useLoad(api.documents, ready);
  const docsById = useMemo(() => new Map<string, DocumentInfo>((docs.data ?? []).map((d) => [d.id, d])), [docs.data]);
  const lastTurnRef = useRef<HTMLLIElement>(null);

  const run = useCallback(async (turn: Turn) => {
    const update = (patch: Partial<Turn>) => setTurns((ts) => ts.map((t) => (t.id === turn.id ? { ...t, ...patch } : t)));
    try {
      const result = await api.ask({ question: turn.question, as_of: turn.as_of, batch: turn.batch });
      update({ status: "done", result });
    } catch (e) {
      update({ status: "error", error: e instanceof ApiError ? e : new ApiError("Something went wrong, try again.", 500, "unknown") });
    }
  }, []);

  const ask = (question: string) => {
    const turn: Turn = {
      id: nextId++,
      question,
      as_of: context.as_of || todayIso(),
      batch: context.batch === "auto" ? null : context.batch,
      startedAt: Date.now(),
      status: "pending",
    };
    setTurns((ts) => [...ts, turn]);
    void run(turn);
  };

  const retry = (turn: Turn) => {
    const again = { ...turn, status: "pending" as const, startedAt: Date.now(), error: undefined };
    setTurns((ts) => ts.map((t) => (t.id === turn.id ? again : t)));
    void run(again);
  };

  // Bring a newly asked question into view.
  useEffect(() => {
    lastTurnRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [turns.length]);

  const openTurn = open ? turns.find((t) => t.id === open.turnId) : undefined;
  const openClaim = open && openTurn?.result ? openTurn.result.claims[open.claimIndex] : undefined;
  const busy = turns.some((t) => t.status === "pending");

  return (
    <div className={`transition-[padding] duration-200 ease-out ${openClaim ? "lg:pr-[420px]" : ""}`}>
      <div className="mx-auto flex min-h-[calc(100vh-57px)] max-w-[720px] flex-col px-4 sm:px-6">
        <div className="flex-1 pt-10 pb-8">
          {turns.length === 0 ? (
            <EmptyState onPick={ask} disabled={!ready} />
          ) : (
            <ol className="space-y-12">
              {turns.map((t, i) => (
                <li key={t.id} ref={i === turns.length - 1 ? lastTurnRef : undefined} className="scroll-mt-6">
                  <TurnView
                    turn={t}
                    activeClaim={open?.turnId === t.id ? open.claimIndex : null}
                    onCite={(claimIndex, trigger) => setOpen({ turnId: t.id, claimIndex, trigger })}
                    onRetry={() => retry(t)}
                  />
                </li>
              ))}
            </ol>
          )}
        </div>
        <Composer health={health} busy={busy} context={context} onContext={setContext} onAsk={ask} />
      </div>
      {openTurn?.result && openClaim && open && (
        <SourcePanel
          key={`${open.turnId}-${open.claimIndex}`}
          number={open.claimIndex + 1}
          claim={openClaim}
          docsById={docsById}
          onClose={() => {
            open.trigger?.focus();
            setOpen(null);
          }}
        />
      )}
    </div>
  );
}
