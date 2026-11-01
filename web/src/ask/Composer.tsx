import { useId, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";
import type { HealthState } from "../lib/hooks";
import { healthMessage, StatusLine } from "../lib/Status";

export interface PolicyContextValue {
  as_of: string;
  batch: "auto" | "2024" | "2025" | "2026";
}

const BATCHES: PolicyContextValue["batch"][] = ["auto", "2024", "2025", "2026"];

function PolicyContext({ value, onChange }: { value: PolicyContextValue; onChange: (v: PolicyContextValue) => void }) {
  const dateId = useId();
  const batchId = useId();
  const helpId = useId();
  return (
    <fieldset className="mb-2" aria-describedby={helpId}>
      <legend className="sr-only">Policy context</legend>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-small text-ink-2">
        <span aria-hidden className="label hidden sm:inline">Policy context</span>
        <label htmlFor={dateId} className="flex items-center gap-2">
          As of
          <input
            id={dateId}
            type="date"
            required
            value={value.as_of}
            onChange={(e) => onChange({ ...value, as_of: e.target.value })}
            className="field h-7 px-1.5 font-mono text-mono"
          />
        </label>
        <label htmlFor={batchId} className="flex items-center gap-2">
          <span>
            <span className="sm:hidden">Batch</span>
            <span className="hidden sm:inline">Admission batch</span>
          </span>
          <select
            id={batchId}
            value={value.batch}
            onChange={(e) => onChange({ ...value, batch: e.target.value as PolicyContextValue["batch"] })}
            className="field h-7 px-1.5 text-small"
          >
            {BATCHES.map((b) => (
              <option key={b} value={b}>
                {b === "auto" ? "Auto" : b}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p id={helpId} className="mt-1 text-label text-ink-3">
        Rules can differ by date and by the year you were admitted.
        <span className="hidden sm:inline"> Auto uses a batch year if your question mentions one.</span>
      </p>
    </fieldset>
  );
}

interface Props {
  health: HealthState;
  busy: boolean;
  context: PolicyContextValue;
  onContext: (v: PolicyContextValue) => void;
  onAsk: (q: string) => void;
}

export function Composer({ health, busy, context, onContext, onAsk }: Props) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const notReady = healthMessage(health);
  const canSend = !notReady && text.trim().length > 0 && !busy;

  // Grow with the text up to ~6 lines.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!canSend) return;
    onAsk(text.trim());
    setText("");
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="sticky bottom-0 -mx-4 border-t border-rule bg-paper/95 px-4 pt-3 pb-4 backdrop-blur-[2px] sm:-mx-6 sm:px-6">
      <PolicyContext value={context} onChange={onContext} />
      {notReady && (
        <div className="mb-2">
          <StatusLine health={health} />
        </div>
      )}
      <form onSubmit={submit} className="field flex items-end gap-2 p-1.5 pl-3 focus-within:border-accent">
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <textarea
          id="question"
          ref={ref}
          rows={1}
          value={text}
          disabled={!!notReady}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKey}
          placeholder={notReady ? "Available once the documents have loaded" : "Ask a question…"}
          maxLength={500}
          className="min-h-[34px] flex-1 resize-none bg-transparent py-1.5 text-[15px] leading-snug text-ink outline-none placeholder:text-ink-3 focus-visible:outline-none disabled:cursor-not-allowed"
        />
        <button type="submit" disabled={!canSend} className="btn btn-primary h-[34px] px-3" aria-label="Ask">
          <span className="hidden sm:inline">Ask</span>
          <ArrowUp size={16} aria-hidden />
        </button>
      </form>
      <p className="mt-1.5 hidden text-label text-ink-3 sm:block">
        Enter to send · Shift+Enter for a new line · Answers come only from the official documents and may be wrong.
      </p>
    </div>
  );
}
