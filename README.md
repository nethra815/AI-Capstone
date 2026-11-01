# SPIT college bot: text-layer PDF pipeline

Answers questions from the college PDFs in `data/pdfs/`. Every document, its metadata, its clauses, and any
circular amendments are read from those PDFs at startup. Nothing is pre-built or hand-written.

## Setup
    pip install -r requirements.txt
    cp .env.example .env                    # then edit .env and set GROQ_API_KEY
    python verify_setup.py                  # PASS/FAIL for each step

Settings come from `.env` (or real environment variables, which take priority). `.env` is git-ignored.

## Ask
    python ask.py "What is the minimum attendance required in each course?" [--as-of 2026-11-01] [--batch 2025] [--json]
    python ask.py --interactive       # initialize once, then ask multiple questions

The first question in a process initializes the PDF index, embeddings, reranker, and amendment extraction.
Use interactive mode or reuse `spitrag.pipeline.get_pipeline()` from an application to avoid rebuilding them.

## Adding documents
Drop any text-layer PDF into `data/pdfs/` (or set `SPIT_DOCS_DIR`). Scanned PDFs (no text layer) are skipped
with a warning. OCR is disabled.

## Metadata
Read from each PDF's own block when present (Document ID, Publication Date, Effective Date, Version,
Supersedes, Superseded by, batches admitted). Otherwise the file name is the id and the document applies at any date.

## Limits
- Circular amendments are extracted by the Groq-hosted LLM. Each one is kept only if its quote and clause numbers
  appear in the PDF text. If a circular gives only before/after values, the pipeline can infer a target clause
  from the matching source passage; unverifiable targets are rejected.
- The benchmark in `eval/` was written for the earlier SPIT regulation set and needs new questions for these PDFs.

## Architecture
1. `pdf_source.py` loads text-layer PDFs and skips scanned pages.
2. `docmeta.py` extracts document identity, dates, versions, and supersession.
3. `ingest.py` creates clause-level chunks.
4. `amendments.py` extracts and validates circular changes.
5. `retrieve.py` combines BM25, dense retrieval, and cross-encoder reranking.
6. `pipeline.py` applies date/batch rules, verifies citations, and abstains when evidence is weak.
7. `generate.py` asks the LLM for structured claims grounded in retrieved passages.

## Testing
Run `python verify_setup.py` for the eight setup and end-to-end checks. Run
`python eval/run_eval.py --split test --modes evidence_aware` for benchmark evaluation.
