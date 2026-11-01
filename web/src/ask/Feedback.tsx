import { useId, useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { api, type Outcome } from "../api";

type Phase = "idle" | "comment" | "sending" | "sent" | "failed";

export function Feedback({ question, outcome }: { question: string; outcome: Outcome }) {
  const [helpful, setHelpful] = useState<boolean | null>(null);
  const [comment, setComment] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const commentId = useId();

  const send = async () => {
    if (helpful == null) return;
    setPhase("sending");
    try {
      await api.feedback({ question, outcome, helpful, comment: comment.trim() || undefined });
      setPhase("sent");
    } catch {
      setPhase("failed");
    }
  };

  if (phase === "sent") return <p className="text-small text-ink-3">Thanks, your feedback was recorded.</p>;

  const thumb = (value: boolean) => {
    const Icon = value ? ThumbsUp : ThumbsDown;
    const on = helpful === value;
    return (
      <button
        type="button"
        aria-pressed={on}
        aria-label={value ? "Helpful" : "Not helpful"}
        onClick={() => {
          setHelpful(value);
          setPhase("comment");
        }}
        className={`rounded-sm p-1.5 transition-colors duration-150 ${on ? "bg-accent-tint text-accent" : "text-ink-3 hover:text-ink"}`}
      >
        <Icon size={16} aria-hidden />
      </button>
    );
  };

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <div className="flex items-center gap-1">
        <span className="mr-1 text-small text-ink-3">Was this useful?</span>
        {thumb(true)}
        {thumb(false)}
      </div>
      {phase !== "idle" && (
        <div className="flex w-full animate-fade-in flex-col gap-2 sm:w-72">
          <label className="sr-only" htmlFor={commentId}>
            Comment (optional)
          </label>
          <textarea
            id={commentId}
            rows={2}
            maxLength={1000}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional comment. Please leave out personal details."
            className="field resize-none px-2 py-1.5 text-small"
          />
          <div className="flex items-center justify-end gap-2">
            {phase === "failed" && <span className="text-label text-changed">Could not send. Try again.</span>}
            <button type="button" onClick={send} disabled={phase === "sending"} className="btn btn-quiet py-1 text-small">
              {phase === "sending" ? "Sending…" : "Send feedback"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
