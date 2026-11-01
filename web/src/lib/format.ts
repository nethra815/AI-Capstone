const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-07-01" -> "1 Jul 2026" (no timezone shifts: the date is parsed as plain text). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
}

export function todayIso(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export const pct = (x: number | null | undefined, digits = 0) =>
  x == null ? "—" : `${(x * 100).toFixed(digits)}%`;

export const seconds = (ms: number | null | undefined) => (ms == null ? "—" : `${(ms / 1000).toFixed(1)} s`);

/** Clause labels from the PDFs sometimes include numbers that are not clauses (e.g. "65.00", "74.99"). */
export function clauseLabels(clauses: string[]): string[] {
  const real = clauses.filter((c) => /^\d{1,2}(\.\d{1,2}){0,3}$/.test(c) && Number(c.split(".")[0]) <= 30);
  return real.length ? real : clauses;
}

export const MODE_LABELS: Record<string, string> = {
  vector: "Vector",
  hybrid: "Hybrid",
  hybrid_rerank: "Hybrid + rerank",
  evidence_aware: "Evidence-aware",
};
