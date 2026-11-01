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

## Web app (SPIT Campus Assistant)
A FastAPI backend (`api/`) wraps the pipeline, and a Vite + React frontend (`web/`) provides the Ask, Documents and
Research views. Run both in two terminals from the project root:

    # 1. backend (needs .env with GROQ_API_KEY; first start takes ~2 minutes while documents and models load)
    pip install -r requirements.txt
    uvicorn api.main:app --reload --port 8000

    # 2. frontend (Node 18+)
    cd web && npm install && npm run dev      # open http://localhost:5173

The frontend proxies `/api` to port 8000, so no extra configuration is needed. The page shows a loading line and
keeps the question box disabled until `/api/health` reports the pipeline is ready.

API endpoints: `GET /api/health`, `POST /api/ask` (`{question, as_of?, batch?, mode?}`), `GET /api/documents`,
`GET /api/documents/{doc_id}/pdf`, `GET /api/chunks/{chunk_id}`, `POST /api/feedback` (appends to
`data/feedback.jsonl`, no personal data), `GET /api/eval` (summary of `eval/results/per_question.csv`).

Notes:
- The free Groq tier allows roughly 4 questions a minute. The API waits and retries once on a short rate limit,
  otherwise the page shows "try again in N seconds" with a retry button.
- In `npm run dev`, typing `dev:conflict` shows a fixture of the "Policy changed" view (the live pipeline only
  returns conflicts when circular amendments were extracted at startup). The fixture is not in production builds.
- `npm run build` writes a static build to `web/dist/`.

## Hinglish and Hindi
Questions in Hinglish or Hindi (Devanagari) are rewritten to a short English search query by one LLM call
(temperature 0); that query drives retrieval, the evidence-coverage check and generation, and is returned as
`english_query`. If the call fails, a built-in word gloss is used instead. Answers are always written in English,
because every claim is verified word-by-word against the English source passages.

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
