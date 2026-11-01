"""Version and policy service: which document applies on a date for a batch, and which circular amendments are
active, upcoming, or irrelevant. All inputs come from the documents themselves."""
import re
from datetime import date

BATCH_TEXT = re.compile(r"\bbatch(?:es)?\b|\badmitted\b|\badmission\b", re.I)


def D(s):
    return date.fromisoformat(s) if s else None


def _legacy(doc) -> set:
    return {int(b) for b in (doc.get("legacy_batches") or "").split(";") if b}


def is_batch_dependent(chunk: dict) -> bool:
    return bool(BATCH_TEXT.search(chunk["text"]))


def amendment_index(amendments):
    return {a["id"]: a for a in amendments}


def applicability(doc: dict, chunk: dict, as_of: date, batch, docs: dict, amend_by_id: dict) -> str:
    """current | superseded | not_yet_effective | not_applicable_batch"""
    ef, et = D(doc["effective_from"]), D(doc.get("effective_to"))
    if ef and as_of < ef:
        return "not_yet_effective"
    dependent = is_batch_dependent(chunk)
    if et and as_of > et:  # expired edition: still governs legacy batches for their provisions
        return "current" if (batch and int(batch) in _legacy(doc) and dependent) else "superseded"
    legacy_all = set().union(*[_legacy(d) for d in docs.values() if d["family"] == doc["family"]])
    if dependent and batch and int(batch) in legacy_all and not _legacy(doc):
        return "not_applicable_batch"
    ids = chunk.get("amend_ids") or []
    if ids and all(D(amend_by_id[i]["effective_from"]) > as_of for i in ids):
        return "not_yet_effective"  # circular text describing a change that has not started
    return "current"


def amendments_for_chunk(chunk: dict, as_of: date, amendments: list):
    """Amendments that target this chunk's clause. Returns (active, upcoming)."""
    active, upcoming = [], []
    for a in amendments:
        for t in a["targets"]:
            if t["doc_id"] != chunk["doc_id"] or t["clause"] not in chunk["clauses"]:
                continue
            if t.get("match") and not re.search(t["match"], chunk["text"]):
                continue
            (active if D(a["effective_from"]) <= as_of else upcoming).append((a, t["clause"]))
            break
    return active, upcoming
