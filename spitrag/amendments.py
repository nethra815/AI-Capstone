"""Extract circular amendments from the circular PDF with the LLM, then check every one against the source.

The LLM proposes structured amendments. An amendment is kept only if:
  * its evidence_quote appears in the circular's text after normalisation (case, whitespace, quotes, dashes,
    line-break hyphens), or a window of the circular text matches it with similarity >= 0.90, in which case the
    real circular text replaces the model's quote,
  * its effective_from is a valid ISO date,
  * each target document id exists in the corpus and each target clause number appears in that document.
Rejected proposals are sent back to the model once with the reason; the retry goes through the same checks.
Every kept and rejected proposal is logged, never silently used.
"""
import copy
import datetime as dt
import difflib
import re
import sys

from .llm import chat_json
from .ingest import build_chunks
from .text import stem, tokens_stem

FUZZY_MIN = 0.90

PROMPT = """You extract amendments from an official college circular. The circular text is OCR output and may have
small errors (for example '%750' for '750', or 'ina' for 'in a'). Read the amendments section and return ONLY a JSON
object, no prose and no code fences:
{"amendments":[{"item":<int>,"subject":"<short name>","summary":"<one sentence>",
  "old_value":"<earlier provision, quoted or closely paraphrased>","new_value":"<revised provision>",
  "effective_from":"YYYY-MM-DD","evidence_quote":"<a SHORT phrase copied exactly from the circular that states the change>",
  "targets":[{"doc_id":"<document id as written in the circular>","clause":"<clause number such as 4.5.2>",
              "match":"<optional regex that must appear in that clause's text, or null>"}]}]}
Rules: use only information in the circular. Do not invent dates or clauses. Number items in the order the circular
lists them, starting at 1. effective_from must be an ISO date. Take it from the 'Effective from' column or the
circular's stated effective date. If that cell names a term rather than a date ('Sem I 2026-27 onwards' for a term
already under way), use the circular's publication date; a month ('May 2027 onwards') means the first day of that
month; 'Results after 1 Dec 2026' means 2026-12-01. evidence_quote must be copied character for character from the
circular text, for example the revised value and the words next to it in the same table row; keep it under 15 words.
Only include amendments that change a rule or a date. The circular may identify a change only by subject and
before/after values; in that case set clause to null rather than inventing one, and the application will match it to
the target document."""

RETRY = """Some amendments you proposed were rejected by an automatic check. For each one below, return a corrected
version, or leave it out if the circular does not support it. Copy evidence_quote character for character from the
circular text (a short phrase, under 15 words). Use the same JSON format: {"amendments":[...]}.

REJECTED:
"""

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTES = {ord("‘"): "'", ord("’"): "'", ord("‛"): "'", ord("′"): "'", ord("`"): "'",
           ord("“"): '"', ord("”"): '"', ord("‟"): '"', ord(" "): " "}


def _norm(s: str) -> str:
    s = s.translate(_DASHES).translate(_QUOTES).lower().replace("%", "")
    s = re.sub(r"[₹¥$€£]", "", s)
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    s = re.sub(r"\s*-\s*", "-", s)  # "26 - 30", "26-30" and "re-<line break>evaluation" compare equal
    return re.sub(r"\s+", " ", s).strip()


def _find_quote(quote: str, text: str, text_norm: str):
    """Return (circular text to store, how it matched) or (None, best similarity)."""
    q = _norm(quote)
    if len(q) < 4:
        return None, 0.0
    if q in text_norm:
        return quote, "exact"
    # Fuzzy: compare the quote with every window of about the same number of words in the circular.
    words = re.sub(r"-\s*\n\s*", "-", text.translate(_DASHES)).split()
    norm_words = [_norm(w) for w in words]
    qn = q.split()
    q_nums = set(re.findall(r"\d+(?:\.\d+)?", q))
    best, best_span = 0.0, None
    for size in {max(1, len(qn) + d) for d in (-2, -1, 0, 1, 2, 3)}:
        for i in range(0, max(1, len(words) - size + 1)):
            cand = " ".join(w for w in norm_words[i:i + size] if w)
            if not q_nums <= set(re.findall(r"\d+(?:\.\d+)?", cand)):
                continue  # a window missing any of the quote's numbers can't stand in for it
            sm = difflib.SequenceMatcher(None, q, cand, autojunk=False)
            if sm.quick_ratio() <= best:
                continue
            ratio = sm.ratio()
            if ratio > best:
                best, best_span = ratio, (i, i + size)
    if best >= FUZZY_MIN:
        return " ".join(words[best_span[0]:best_span[1]]), f"fuzzy {best:.2f}"
    return None, best


def _call_llm(circular_text: str, known_docs: list[str], retry_note: str | None = None) -> dict:
    user = f"Known document ids: {', '.join(known_docs)}\n\nCIRCULAR TEXT:\n{circular_text}"
    if retry_note:
        user += "\n\n" + RETRY + retry_note
    return chat_json(PROMPT, user, max_tokens=4000, required_key="amendments", temperature=0,
                     reasoning_effort="low", max_wait=65)


GENERIC_SUBJECT = {"cap", "fee", "fees", "limit", "window", "change", "rules", "rule", "schedule", "revised", "date",
                   "dates", "period", "with", "from", "for", "and", "the"}
NUM = re.compile(r"\d+(?:\.\d+)?")


def _target_supported(a: dict, doc_id: str, clause: str, chunks: list[dict]) -> bool:
    """True if a passage of that clause states the earlier provision: it has every number in old_value and at least two
    of the subject's specific words (one, if the subject has only one). Stops a change landing on an unrelated clause
    that merely shares a number, such as a fee of the same amount."""
    nums = set(NUM.findall(_norm(str(a.get("old_value") or ""))))
    subject = {stem(w) for w in re.findall(r"[a-z]+", _norm(str(a.get("subject") or "")))
               if len(w) > 3 and w not in GENERIC_SUBJECT}
    need = min(2, len(subject))
    for c in chunks:
        if c["doc_id"] != doc_id or clause not in c["clauses"]:
            continue
        text = _norm(f"{c['heading']}\n{c['text']}")
        if nums and not nums <= set(NUM.findall(text)):
            continue
        if len(subject & set(tokens_stem(text))) < need:
            continue
        return True
    return False


def _check(a: dict, circular_text: str, cnorm: str, documents: dict, chunks: list[dict], corpus_norm: dict,
           named_docs: list[str]):
    """Validate one proposal in place. Returns None if it is kept, otherwise the rejection reason."""
    quote, how = _find_quote(str(a.get("evidence_quote") or ""), circular_text, cnorm)
    reason = None
    if quote is None:
        reason = f"evidence_quote not found in circular (best similarity {how:.2f})"
    else:
        a["evidence_quote"], a["quote_match"] = quote, how
    try:
        dt.date.fromisoformat(a["effective_from"])
    except (KeyError, TypeError, ValueError):
        reason = reason or f"invalid effective_from {a.get('effective_from')!r}"
    valid_targets, target_errors = [], []
    for t in a.get("targets") or []:
        doc_id, clause = t.get("doc_id"), t.get("clause")
        if t.get("match"):
            try:
                re.compile(t["match"])
            except re.error:
                t["match"] = None  # an unusable regex narrows nothing; the clause check below still applies
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
            if _target_supported(a, doc_id, clause, chunks):
                # "7" when only clause 7.3 states the provision: narrow it, so the rest of section 7 stays current
                subs = {l for c in chunks if c["doc_id"] == doc_id for l in c["clauses"] if l.startswith(clause + ".")}
                narrower = [s for s in sorted(subs) if _target_supported(a, doc_id, s, chunks)]
                if len(narrower) == 1:
                    t["clause"] = narrower[0]
                valid_targets.append(t)
            else:
                target_errors.append(f"clause {clause} of {doc_id} does not state the earlier provision")
        elif doc_id in documents:
            target_errors.append(f"clause {clause} not found in {doc_id}")
    # The model sometimes leaves out a document the circular amends. Look for the earlier provision in every document
    # the circular names; a clause found this way passes the same checks as one the model proposed.
    # Only for before/after values with numbers (a fee, a date, a cap), which can be matched reliably.
    targeted = {t["doc_id"] for t in valid_targets}
    for doc_id in named_docs if NUM.search(str(a.get("old_value") or "")) else []:
        if doc_id in targeted:
            continue
        clause = _infer_clause(a, doc_id, chunks)
        if clause and _target_supported(a, doc_id, clause, chunks):
            valid_targets.append({"doc_id": doc_id, "clause": clause, "match": None, "inferred": True})
    a["targets"] = valid_targets
    if target_errors and not valid_targets:
        reason = reason or target_errors[0]
    if not reason and not valid_targets:
        reason = "no valid targets"
    return reason


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


def _brief(a: dict) -> str:
    return (f"item {a.get('item')} {a.get('subject')!r}: {a.get('old_value')!r} -> {a.get('new_value')!r}, "
            f"effective {a.get('effective_from')}, targets "
            + ", ".join(f"{t.get('doc_id')} cl. {t.get('clause')}" for t in a.get("targets") or []))


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
        # documents this circular names and that are still in force: the only ones it can amend
        named = [d for d in documents if d != circ["doc_id"] and d in text and not documents[d].get("superseded_by")]
        kept, rejected = {}, []
        for a in _call_llm(text, list(documents))["amendments"]:
            proposed = copy.deepcopy(a)
            reason = _check(a, text, cnorm, documents, chunks, corpus_norm, named)
            if reason:
                rejected.append((proposed, reason))
            else:
                kept[a.get("item")] = a
        if rejected:  # one retry, telling the model exactly what failed
            note = "\n".join(f"- {_brief(a)}; quote {a.get('evidence_quote')!r}; REASON: {r}" for a, r in rejected)
            for a, r in rejected:
                print(f"[amendments] {circ['doc_id']} rejected (first pass) {_brief(a)}: {r}", file=sys.stderr)
            try:
                retried = _call_llm(text, list(documents), retry_note=note)["amendments"]
            except RuntimeError as e:
                print(f"[amendments] retry failed: {e}", file=sys.stderr)
                retried = []
            rejected = []
            for a in retried:
                if a.get("item") in kept:
                    continue
                reason = _check(a, text, cnorm, documents, chunks, corpus_norm, named)
                if reason:
                    rejected.append((a, reason))
                else:
                    kept[a.get("item")] = a
            for a, r in rejected:
                print(f"[amendments] {circ['doc_id']} rejected {_brief(a)}: {r}", file=sys.stderr)
        for item in sorted(kept, key=lambda x: (not isinstance(x, int), x)):
            a = kept[item]
            a["id"] = f"{circ['doc_id']}#{a['item']}"
            a["circular"] = circ["doc_id"]
            a["hints"] = []
            out.append(a)
            print(f"[amendments] {circ['doc_id']} kept {_brief(a)} (quote {a['quote_match']})", file=sys.stderr)
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
