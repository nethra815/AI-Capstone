import type { HealthState } from "./hooks";

/** Plain sentence describing why the assistant can't be used yet, or null when it is ready. */
export function healthMessage(h: HealthState): string | null {
  switch (h.status) {
    case "ready":
      return null;
    case "checking":
      return "Connecting to the assistant…";
    case "offline":
      return h.message;
    case "failed":
      return `The assistant could not start: ${h.message}`;
    case "loading":
      if (h.attempt > 1) return `Still loading: the first attempt to reach the language model failed, retrying (attempt ${h.attempt}).`;
      return `Loading the official documents and search models${h.seconds != null ? ` (${Math.round(h.seconds)} s)` : ""}. This takes about two minutes after the server starts.`;
  }
}

export function StatusLine({ health }: { health: HealthState }) {
  const msg = healthMessage(health);
  if (!msg) return null;
  const bad = health.status === "failed" || health.status === "offline";
  return (
    <p role="status" className={`flex items-center gap-2 text-small ${bad ? "text-changed" : "text-ink-2"}`}>
      <span
        aria-hidden
        className={`inline-block size-1.5 rounded-full ${bad ? "bg-changed" : "bg-ink-3 motion-safe:animate-pulse"}`}
      />
      {msg}
    </p>
  );
}
