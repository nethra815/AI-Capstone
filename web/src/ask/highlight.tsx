import type { ReactNode } from "react";

const STOP = new Set(
  "the and for are was were with that this from have has had not but any all its per each must shall will may can into than then they their there which what when where who whom been being also only such upon under over".split(
    " ",
  ),
);

export const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Content words and numbers worth highlighting. */
export function keyTerms(text: string): string[] {
  const words = text.toLowerCase().match(/[\p{L}\p{N}][\p{L}\p{N}.,:%₹-]*/gu) ?? [];
  const terms = new Set<string>();
  for (let w of words) {
    w = w.replace(/[.,:]+$/, "");
    if (/\d/.test(w) || (w.length > 3 && !STOP.has(w))) terms.add(w);
  }
  return [...terms];
}

/** Wrap occurrences of `terms` in <mark>. Matching is case-insensitive and on word starts. */
export function Highlight({ text, terms }: { text: string; terms: string[] }) {
  if (!terms.length) return <>{text}</>;
  const esc = [...terms].sort((a, b) => b.length - a.length).map(escapeRegExp);
  const re = new RegExp(String.raw`(?<![\p{L}\p{N}])(` + esc.join("|") + ")", "giu");
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) out.push(text.slice(last, i));
    out.push(<mark key={i}>{m[0]}</mark>);
    last = i + m[0].length;
  }
  out.push(text.slice(last));
  return <>{out}</>;
}
