"""Document metadata read from each PDF itself. Works for any college document.

Fields are taken from a 'Document ID / Publication Date / Effective Date / Version / Supersedes' block when present.
Documents without one still load: the id falls back to the file name and dates stay empty, so they apply at any date.
"""
import re
from datetime import date, datetime, timedelta

ID_PAT = r"[A-Z][A-Za-z]+(?:[/-][A-Za-z0-9][A-Za-z0-9.-]*){2,}"  # e.g. SPIT/ACAD/ARH/2026-27/01 or ACC-FEE-001
DATE_PAT = r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})"


def _date(s):
    if not s:
        return None
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(re.sub(r"\s+", " ", s.strip()), fmt).date()
        except ValueError:
            pass
    return None


def _first(pattern, text, flags=re.I | re.M):
    m = re.search(pattern, text, flags)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


# Field names used in the documents' metadata tables; a title value ends where the next field begins.
FIELD_LABELS = {"document id", "issuing department", "approving authority", "approving body", "version",
                "publication date", "effective date", "supersedes", "superseded by", "status", "related documents",
                "applicable academic year", "approved by", "ratified by", "amends", "keywords", "field", "details",
                "category", "authorised signatories", "reissued", "relationship"}
INSTITUTION = re.compile(r"institute of technology|\(spit\)", re.I)
NOT_A_TITLE = re.compile(
    r"synthetic|research|fictional|not an actual|archived|^document control$|^details$|^field$|^page\s+\d+|"
    r"^version\b|^academic year\b|^undergraduate programmes|\|", re.I)


def _title_field(lines):
    """Value of a 'Document Title' or 'Title' row in the metadata table, which may wrap onto the next line."""
    for i, line in enumerate(lines):
        if line.lower() not in ("document title", "title"):
            continue
        parts = []
        for nxt in lines[i + 1:i + 3]:
            if nxt.lower() in FIELD_LABELS:
                break
            # a wrapped value continues after "(2026–" or "... and", or with a parenthetical such as "(2026–27)"
            if parts and not (re.search(r"[(–-]$|\band$", parts[-1]) or nxt.startswith("(")):
                break
            parts.append(nxt)
        title = ""
        for p in parts:
            title += p if re.search(r"[(–-]$", title) else (" " if title else "") + p
        if title and not re.fullmatch(ID_PAT, title):
            return title
    return None


def _title(pages):
    lines = [l.strip() for l in pages[0].splitlines() if l.strip()]
    found = _title_field(lines[:40])
    if found:
        return found
    for line in lines[:15]:  # otherwise the first line that is not page furniture, the institution, an id or a number
        if (len(line.split()) >= 2 and re.search(r"[A-Za-z]{3}", line) and not NOT_A_TITLE.search(line)
                and not INSTITUTION.search(line) and not re.fullmatch(ID_PAT, line)):
            return line
    return None


def parse_document(pdf: dict) -> dict:
    full = "\n".join(pdf["pages"])
    doc_id = _first(r"Document ID\s+(" + ID_PAT + ")", full) or pdf["file"].rsplit(".", 1)[0]
    parts = doc_id.split("/")
    family = parts[2] if len(parts) >= 4 else "DOC"  # e.g. ARH, CIR; generic docs get 'DOC'
    title = _title(pdf["pages"]) or pdf["file"]
    pub = _date(_first(r"Publication\s+(?:Date\s+)?" + DATE_PAT, full))
    eff = _date(_first(r"Effective\s+Date\s+" + DATE_PAT, full)) or pub
    version = _first(r"^Version\s+(\d+(?:\.\d+)?)", full) or "?"
    supersedes = _first(r"Supersedes\s+(" + ID_PAT + ")", full)
    superseded_by = _first(r"Superseded by\s+(" + ID_PAT + ")", full)
    superseded_on = _date(_first(r"Superseded on\s+" + DATE_PAT, full))
    m = re.search(r"batches admitted in\s+(\d{4})-\d{2}\s+and\s+(\d{4})-\d{2}", full, re.I)
    legacy = sorted({int(g) for g in m.groups()}) if m else []
    is_circular = "circular" in title.lower() or "/CIR/" in doc_id or "-CIR-" in doc_id
    return {
        "doc_id": doc_id, "family": family, "title": title, "version": version, "file": pdf["file"],
        "doc_type": "circular" if is_circular else "document",
        "published_on": pub.isoformat() if pub else None,
        "effective_from": eff.isoformat() if eff else None,
        "effective_to": (superseded_on - timedelta(days=1)).isoformat() if superseded_on else None,
        "supersedes": supersedes, "superseded_by": superseded_by,
        "legacy_batches": ";".join(str(b) for b in legacy), "n_pages": pdf["n_pages"],
    }


def link_supersession(docs: dict) -> dict:
    """Set effective_to on an older document from the newer one that names it in 'Supersedes'."""
    for d in docs.values():
        if d["supersedes"] in docs and d["effective_from"]:
            old = docs[d["supersedes"]]
            if not old["effective_to"]:
                old["effective_to"] = (date.fromisoformat(d["effective_from"]) - timedelta(days=1)).isoformat()
    return docs


def build_documents(pdfs: list[dict]) -> dict:
    docs = {}
    for p in pdfs:
        d = parse_document(p)
        docs[d["doc_id"]] = d
    return link_supersession(docs)
