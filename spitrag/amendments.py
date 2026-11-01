"""Extract circular amendments from the circular PDF with the LLM, then check every one against the source.

The LLM proposes structured amendments. An amendment is kept only if:
  * its evidence_quote appears verbatim (after whitespace/case normalisation) in the circular's OCR text,
  * its effective_from is a valid ISO date,
  * each target document id exists in the corpus and each target clause number appears in that document.
Rejected proposals are reported, never silently used.
"""
import datetime as dt
import re
import sys

from .llm import chat_json
from .ingest import build_chunks

PROMPT = """You extract amendments from an official college circular. The circular text is OCR output and may have
small errors (for example '%750' for '750', or 'ina' for 'in a'). Read the amendments section and return ONLY a JSON
object, no prose and no code fences:
{"amendments":[{"item":<int>,"subject":"<short name>","summary":"<one sentence>",
  "old_value":"<earlier provision, quoted or closely paraphrased>","new_value":"<revised provision>",
  "effective_from":"YYYY-MM-DD","evidence_quote":"<a SHORT phrase copied exactly from the circular that states the change>",
  "targets":[{"doc_id":"<document id as written in the circular>","clause":"<clause number such as 4.5.2>",
              "match":"<optional regex that must appear in that clause's text, or null>"}]}]}
Rules: use only information in the circular. Do not invent dates or clauses. If an item's effective date is stated as
'Results declared on or after 1 Dec 2026', use the first day of that window only if the circular says so; otherwise
use the date given in the 'Effective from' column. Only include amendments that change a rule or a date. The circular
may identify a change only by subject and before/after values; in that case set clause to null rather than inventing
one, and the application will match it to the target document."""


def _norm(s: str) -> str:
    s = s.lower().replace("–", "-").replace("—", "-").replace("%", "")
    s = re.sub(r"[₹¥$€£]", "", s)
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _call_llm(circular_text: str, known_docs: list[str]) -> dict:
    return chat_json(PROMPT, f"Known document ids: {', '.join(known_docs)}\n\nCIRCULAR TEXT:\n{circular_text}",
                     max_tokens=8000, required_key="amendments")


def _infer_clause(amendment: dict, doc_id: str, chunks: list[dict]) -> str | None:
    """Resolve table-only circular entries against a target document's clause text."""
    subject = set(re.findall(r"[a-z0-9]+", _norm(amendment.get("subject", ""))))
    generic_subject = {"cap", "fee", "limit", "window", "change", "rules"}
    values = [_norm(amendment.get(key, "")) for key in ("old_value", "new_value")]
    values = [value for value in values if len(value) >= 4]
    numeric_values = set(re.findall(r"\d+(?:\.\d+)?", " ".join(values)))
    candidates = []
    for chunk in chunks:
        if chunk["doc_id"] != doc_id:
            continue
        text = _norm(chunk["text"])
        chunk_words = set(re.findall(r"[a-z0-9]+", text))
        phrase_hits = sum(value in text for value in values)
        subject_matches = subject & chunk_words
        subject_hits = sum(2 if word not in generic_subject else 1 for word in subject_matches)
        numeric_hits = bool(numeric_values & set(re.findall(r"\d+(?:\.\d+)?", text)))
        if not phrase_hits and (not numeric_hits or not subject_hits):
            continue
        value_hits = phrase_hits or int(numeric_hits)
        specificity = max((label.count(".") for label in chunk["clauses"]), default=-1)
        candidates.append((value_hits, subject_hits, specificity, chunk))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    best = candidates[0][3]
    return max(best["clauses"], key=lambda label: label.count("."), default=None)


def extract_amendments(documents: dict, pdfs: list[dict]) -> list[dict]:
    circulars = [d for d in documents.values() if d["doc_type"] == "circular"]
    if not circulars:
        return []
    out = []
    by_file = {p["file"]: p for p in pdfs}
    chunks = build_chunks(pdfs, documents)
    corpus_norm = {d["doc_id"]: _norm("\n".join(by_file[d["file"]]["pages"])) for d in documents.values()}
    for circ in circulars:
        pdf = by_file[circ["file"]]
        text = "\n".join(f"[page {i}]\n{t}" for i, t in enumerate(pdf["pages"], 1))
        cnorm = _norm(text)
        proposed = _call_llm(text, list(documents))["amendments"]
        for a in proposed:
            reason = None
            q = _norm(a.get("evidence_quote", ""))
            if len(q) < 4 or q not in cnorm:
                reason = "evidence_quote not found verbatim in circular"
            try:
                dt.date.fromisoformat(a["effective_from"])
            except (KeyError, TypeError, ValueError):
                reason = reason or "invalid effective_from"
            valid_targets = []
            target_errors = []
            for t in a.get("targets", []):
                doc_id = t.get("doc_id")
                clause = t.get("clause")
                if not isinstance(doc_id, str) or not doc_id:
                    target_errors.append("invalid target document id")
                elif doc_id not in documents:
                    target_errors.append(f"unknown target document {doc_id}")
                elif not isinstance(clause, str) or not clause:
                    clause = _infer_clause(a, doc_id, chunks)
                    if clause:
                        t["clause"] = clause
                    else:
                        target_errors.append(f"invalid clause for target document {doc_id}")
                if (isinstance(clause, str) and clause and doc_id in documents
                        and re.search(r"(?<![\d.])" + re.escape(clause) + r"(?![\d])", corpus_norm[doc_id])):
                    valid_targets.append(t)
                elif doc_id in documents:
                    target_errors.append(f"clause {clause} not found in {doc_id}")
            a["targets"] = valid_targets
            if target_errors and not valid_targets:
                reason = reason or target_errors[0]
            if reason or not valid_targets:
                print(f"[amendments] rejected item {a.get('item')}: "
                      f"{reason or 'no valid targets'}", file=sys.stderr)
                continue
            a["id"] = f"{circ['doc_id']}#{a['item']}"
            a["circular"] = circ["doc_id"]
            a["hints"] = []
            out.append(a)
    print(f"[amendments] kept {len(out)} verified amendments from {len(circulars)} circular(s)", file=sys.stderr)
    return out


def attach_amendments(chunks: list[dict], amendments: list[dict]) -> None:
    """Link circular chunks to the amendments they state, and clause-level targets for amendment logic."""
    for c in chunks:
        if c["doc_type"] != "circular":
            continue
        cn = _norm(c["text"])
        for a in amendments:
            if a["circular"] != c["doc_id"]:
                continue
            if _norm(a["evidence_quote"]) in cn or re.search(rf"\bitem\s+{a['item']}\b", c["text"], re.I):
                c["amend_ids"].append(a["id"])
