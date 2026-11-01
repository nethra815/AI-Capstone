// Plain-language wording for pipeline fields. Nothing here invents data: it only rephrases what the API returned.
import type { AskResult } from "../api";
import { escapeRegExp } from "./highlight";

export function friendlyAbstainReason(reason: string | null): string {
  if (!reason) return "The documents did not contain enough evidence to answer.";
  if (reason.startsWith("low evidence coverage"))
    return "The closest passages only partly match your question, so an answer couldn't be confirmed.";
  if (reason.startsWith("generator found the evidence insufficient"))
    return "Related passages were found, but none of them states this directly.";
  if (reason.startsWith("no claim passed citation verification"))
    return "A draft answer was prepared but couldn't be matched to the wording of the sources, so it was withheld.";
  if (reason.startsWith("clarification needed"))
    return "The question is too short or unclear to search reliably. Try adding a little more detail.";
  if (reason.startsWith("no currently applicable evidence"))
    return "Nothing found applies on the chosen date and admission batch.";
  return reason;
}

// Office suggestions keyed on the document code inside passage ids, e.g. SPIT_CA_HST_2026_01_036 -> HST.
const OFFICES: [RegExp, string][] = [
  [/_HST_/, "Hostel Office (Warden)"],
  [/_(ACC|FEE|PAY|REF)_/, "Accounts Office"],
  [/_(SCH|DSA)_/, "Student Affairs Office (scholarships)"],
  [/_TPC_|_PLC_/, "Training and Placement Cell"],
  [/_(EXM|EXAM|ERR)_/, "Examination Cell"],
  [/_LIB_/, "Library front desk"],
  [/_GRV_/, "Grievance Redressal Cell"],
  [/_COC_/, "Student Affairs Office"],
  [/_CLB_/, "Student Activities Office"],
  [/_(ACA|ACAD|ARH|ATT|CND|GCP)_/, "Academic Section"],
];

/** The office most related to the passages the search found, or null if unclear. */
export function suggestedOffice(r: AskResult): string | null {
  const ids = (r.context_ids?.length ? r.context_ids : r.retrieved_ids).slice(0, 5);
  const votes = new Map<string, number>();
  for (const id of ids) {
    const hit = OFFICES.find(([re]) => re.test(id));
    if (hit) votes.set(hit[1], (votes.get(hit[1]) ?? 0) + 1);
  }
  let best: string | null = null;
  let n = 0;
  for (const [office, v] of votes) if (v > n) [best, n] = [office, v];
  return best;
}

export const LANGUAGES: Record<string, string> = { en: "English", hinglish: "Hinglish", hi: "Hindi" };

/** The question with the pipeline's spelling corrections applied, or null if nothing was corrected. */
export function searchedFor(r: AskResult): string | null {
  if (!r.spell_fixes?.length) return null;
  let q = r.question;
  for (const [from, to] of r.spell_fixes) {
    q = q.replace(new RegExp(String.raw`\b` + escapeRegExp(from) + String.raw`\b`, "i"), to);
  }
  return q;
}

/** Distinct documents cited across the kept claims. */
export function citedDocCount(r: AskResult): number {
  return new Set(r.claims.flatMap((c) => c.citations.map((ci) => ci.doc_id))).size;
}
