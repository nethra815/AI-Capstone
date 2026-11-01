import { useEffect, useState } from "react";
import { api, ApiError, type Health } from "../api";

export type HealthState =
  | { status: "checking" }
  | { status: "offline"; message: string }
  | { status: "loading"; seconds: number | null; attempt: number }
  | { status: "failed"; message: string }
  | { status: "ready"; health: Health };

/** Poll /api/health until the pipeline is ready (or failed to start). */
export function useHealth(): HealthState {
  const [state, setState] = useState<HealthState>({ status: "checking" });
  useEffect(() => {
    let stop = false;
    let timer: number | undefined;
    const tick = async () => {
      try {
        const h = await api.health();
        if (stop) return;
        if (h.ready) return setState({ status: "ready", health: h });
        if (h.error) return setState({ status: "failed", message: h.error });
        setState({ status: "loading", seconds: h.loading_seconds, attempt: h.startup_attempt });
      } catch (e) {
        if (stop) return;
        setState({ status: "offline", message: e instanceof ApiError ? e.message : "Can't reach the server." });
      }
      timer = window.setTimeout(tick, 2500);
    };
    tick();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, []);
  return state;
}

/** Whole seconds since `since` (a Date.now() value), updated every second while `active`. */
export function useElapsed(since: number, active: boolean): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  return Math.max(0, Math.floor((now - since) / 1000));
}

export type Route = "ask" | "documents" | "research";
const ROUTES: Route[] = ["ask", "documents", "research"];

function readRoute(): Route {
  const r = window.location.hash.replace(/^#\/?/, "") as Route;
  return ROUTES.includes(r) ? r : "ask";
}

/** Tiny hash router: #/ask, #/documents, #/research. */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(readRoute);
  useEffect(() => {
    const on = () => setRoute(readRoute());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

/** Load once from the API; `reload` retries. */
export function useLoad<T>(load: () => Promise<T>, enabled = true) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    let stop = false;
    setError(null);
    load()
      .then((d) => !stop && setData(d))
      .catch((e) => !stop && setError(e instanceof ApiError ? e.message : "Something went wrong, try again."));
    return () => {
      stop = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, attempt]);
  return { data, error, reload: () => setAttempt((a) => a + 1) };
}
