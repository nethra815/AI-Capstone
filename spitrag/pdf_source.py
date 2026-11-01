"""Read every PDF in DOCS_DIR that has a text layer. Scanned PDFs are skipped with a warning (OCR is not used).

Text is extracted fresh on each run; nothing is written to disk.
"""
import sys
from pathlib import Path

import pymupdf

from .config import DOCS_DIR, TEXT_LAYER_MIN_WORDS


def load_pdf(path: Path):
    doc = pymupdf.open(path)
    pages = [p.get_text() for p in doc]
    scanned = [i + 1 for i, t in enumerate(pages) if len(t.split()) < TEXT_LAYER_MIN_WORDS]
    if scanned:
        print(f"[pdf] SKIPPED {path.name}: no text layer on pages {scanned[:10]}"
              f"{'...' if len(scanned) > 10 else ''} (OCR is disabled)", file=sys.stderr)
        return None
    return {"file": path.name, "pages": pages, "n_pages": len(pages)}


def load_all(docs_dir: Path = DOCS_DIR) -> list[dict]:
    files = sorted(Path(docs_dir).glob("*.pdf"))
    if not files:
        raise SystemExit(f"No PDFs found in {docs_dir}. Put college documents there or set SPIT_DOCS_DIR.")
    loaded = [p for p in (load_pdf(f) for f in files) if p]
    if not loaded:
        raise SystemExit("No PDFs with a text layer were found. Scanned PDFs need OCR, which is disabled.")
    return loaded
