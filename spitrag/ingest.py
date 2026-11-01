"""Turn page text into clause-level chunks that keep page numbers. Built in memory on every run."""
import re

from .config import MAX_CHUNK_WORDS

SECTION = re.compile(r"^(\d+)\.\s+[A-Z][^.]{0,90}$")       # "4. Attendance Rules"
CLAUSE = re.compile(r"^\d+\.\d+(?:\.\d+)*\s+\S")             # "4.3.1 Duty leave ..."
ITEM = re.compile(r"^Items?\s+\d+(?:\s+and\s+\d+|-\d+)?\s*[-–.:]")  # "Item 1 - Duty leave." (circular)
ROW = re.compile(r"^\d{1,2}\s+[A-Z][A-Za-z ]+")              # circular summary-table rows "1 Duty leave cap ..."
CLAUSE_LABEL = re.compile(r"(?<![\d.])(\d+\.\d+(?:\.\d+)*)(?![\d])")
DOC_CONTROL_END = re.compile(r"^\d+\.\s+[A-Z]")


def _starts_unit(line: str, circular: bool) -> bool:
    if CLAUSE.match(line) or ITEM.match(line):
        return True
    return circular and bool(ROW.match(line))


def chunk_document(doc: dict, pdf_pages: list[str]) -> list[dict]:
    prefix = re.sub(r"\W+", "_", doc["doc_id"]).strip("_")
    circular = doc["doc_type"] == "circular"
    lines = []  # (page_no, text)
    for pno, page in enumerate(pdf_pages, 1):
        for raw in page.splitlines():
            line = raw.strip()
            if line:
                lines.append((pno, line))

    chunks, cur, section_no, heading, in_control = [], [], None, "Front matter", True

    def flush():
        nonlocal cur
        if not cur:
            return
        text = "\n".join(t for _, t in cur)
        pages = sorted({p for p, _ in cur})
        kind = "control" if in_control and section_no is None else "body"
        labels = sorted({x for x in CLAUSE_LABEL.findall(text)} | ({section_no} if section_no else set()),
                        key=lambda s: [int(p) for p in s.split(".")])
        idx = len(chunks)
        chunks.append({
            "id": f"{prefix}_{idx:03d}", "doc_id": doc["doc_id"], "family": doc["family"], "doc_type": doc["doc_type"], "title": doc["title"],
            "version": doc["version"], "published_on": doc["published_on"], "effective_from": doc["effective_from"],
            "heading": heading, "section_no": section_no, "kind": kind, "para_type": "para",
            "clauses": labels, "pages": pages, "amend_ids": [], "text": text,
            "index_text": f"{doc['title']} v{doc['version']} | {heading}\n{text}",
        })
        cur = []

    for pno, line in lines:
        m = SECTION.match(line)
        if m and not CLAUSE.match(line):
            flush()
            section_no, heading = m.group(1), line
            in_control = False
            cur = [(pno, line)]
            continue
        if _starts_unit(line, circular) or (cur and sum(len(t.split()) for _, t in cur) > MAX_CHUNK_WORDS):
            flush()
        cur.append((pno, line))
    flush()
    return [c for c in chunks if len(c["text"].split()) >= 3]


def build_chunks(pdfs: list[dict], documents: dict) -> list[dict]:
    by_file = {p["file"]: p for p in pdfs}
    chunks = []
    for d in documents.values():
        chunks.extend(chunk_document(d, by_file[d["file"]]["pages"]))
    return chunks
