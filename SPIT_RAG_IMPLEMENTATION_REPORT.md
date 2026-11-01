# SPIT RAG Pipeline

## Implementation, usage, and test report

**Generated:** 1 November 2026  
**Project:** `spit_rag`

---

## 1. Executive summary

This project answers questions about college regulation PDFs.

The pipeline:

1. Reads regulation PDFs.
2. Extracts document metadata and clauses.
3. Finds relevant passages using BM25 and dense retrieval.
4. Applies document dates, admission batches, versions, and circular amendments.
5. Sends only selected evidence to the LLM.
6. Verifies the generated claims against the source passages.
7. Answers, reports a conflict, or abstains when the evidence is insufficient.

### Current status

| Area | Status |
|---|---|
| Python compilation | Passed |
| Setup and health checks | **8/8 passed** |
| End-to-end question | Passed |
| PDFs loaded | 20 |
| Documents parsed | 20 |
| Clause-level chunks | 728 |
| Verified amendments | 9 in the final health-check run |
| Citation support in focused test | 100% |
| Production readiness | **Not yet** |

The pipeline works technically, but answer accuracy is still experimental. The focused benchmark achieved **30.8% answer accuracy**, so the system should currently be used for research, demos, and supervised testing rather than unsupervised student decisions.

---

## 2. Repository structure

```text
spit_rag/
├── ask.py                         Command-line and interactive interface
├── verify_setup.py                Health and end-to-end checks
├── requirements.txt               Python dependencies
├── README.md                      Quick-start documentation
├── data/
│   └── pdfs/                      Regulation PDFs
├── spitrag/
│   ├── amendments.py              Circular amendment extraction and validation
│   ├── config.py                  Environment and pipeline settings
│   ├── docmeta.py                 Document metadata and supersession
│   ├── generate.py                Grounded answer generation
│   ├── ingest.py                  Clause-level chunking
│   ├── llm.py                     LLM calls and JSON parsing
│   ├── pdf_source.py              PDF loading
│   ├── pipeline.py                Main application pipeline
│   ├── retrieve.py                BM25, dense retrieval, reranking
│   ├── text.py                    Query normalization and tokenization
│   ├── verify.py                  Claim verification
│   └── versions.py                Date, batch, and amendment applicability
└── eval/
    ├── benchmark.jsonl            Benchmark questions
    └── run_eval.py                Evaluation runner
```

---

## 3. Pipeline flow

### Startup flow

When the pipeline is initialized:

```text
PDF files
   ↓
Text extraction
   ↓
Document metadata
   ↓
Clause-level chunks
   ↓
Circular amendment extraction
   ↓
BM25 index + dense embeddings
   ↓
Cross-encoder reranker
   ↓
Ready to answer questions
```

Startup is expensive because it loads the PDFs, builds indexes, and loads transformer models.

The project now provides `get_pipeline()` to reuse the initialized pipeline within the same process.

### Per-question flow

```text
Student question
   ↓
Query normalization and batch detection
   ↓
BM25 + dense retrieval
   ↓
Cross-encoder reranking
   ↓
Date, version, batch, and amendment filtering
   ↓
Evidence context selection
   ↓
LLM generates structured claims
   ↓
Citation and evidence verification
   ↓
Answer / conflict / abstention
```

---

## 4. Main implementation components

### `spitrag/pdf_source.py`

- Loads PDFs from `data/pdfs/`.
- Uses PyMuPDF.
- Requires a text layer.
- Skips scanned PDFs because OCR is disabled.

### `spitrag/docmeta.py`

Extracts:

- Document ID
- Title
- Publication date
- Effective date
- Version
- Superseded document
- Document family
- Legacy batch information

### `spitrag/ingest.py`

Converts source text into chunks while preserving:

- Document ID
- Heading
- Clause labels
- Page numbers
- Original text

### `spitrag/amendments.py`

Processes circular amendments through the LLM and validates:

- Evidence quote
- Effective date
- Target document
- Target clause

If a circular provides only before/after values and no clause number, the implementation attempts to infer the clause from matching source text. If it cannot verify the match, it rejects the amendment instead of guessing.

### `spitrag/retrieve.py`

Provides:

- Vector retrieval
- BM25 retrieval
- Hybrid retrieval
- Cross-encoder reranking

Embedding and reranking models are loaded once per process.

### `spitrag/pipeline.py`

Coordinates:

- Retrieval
- Date and batch filtering
- Amendment handling
- Context construction
- LLM generation
- Claim verification
- Conflict reporting
- Abstention

`get_pipeline()` returns a thread-safe, process-wide shared pipeline.

### `spitrag/llm.py`

Calls the Groq-compatible OpenAI endpoint and parses structured JSON responses.

The parser:

- Finds actual JSON object boundaries.
- Supports responses surrounded by prose or code fences.
- Selects the object containing the required schema key.
- Reports malformed responses clearly.

---

## 5. Installation

Run these commands from the project directory.

### Create an environment

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### Install dependencies

```powershell
pip install -r requirements.txt
```

### Configure the API key

Create a local `.env` file and set:

```text
GROQ_API_KEY=your-key
```

Optional settings:

```text
SPIT_LLM_MODEL=...
SPIT_DOCS_DIR=...
SPIT_EMBED_MODEL=...
SPIT_RERANK_MODEL=...
SPIT_ABSTAIN_COVERAGE=...
```

Do not commit `.env` or API keys. The project already ignores `.env`.

---

## 6. Usage

### Ask one question

```powershell
python ask.py "What is the minimum attendance required in each course?"
```

### Specify policy date and batch

```powershell
python ask.py `
  "What is the condonation fee?" `
  --as-of 2026-11-01 `
  --batch 2025
```

### Ask multiple questions efficiently

```powershell
python ask.py --interactive
```

Example:

```text
Pipeline ready. Ask a question, or type 'exit' to quit.

question> What is the attendance requirement?
question> What is the library fine per book per day?
question> What is the minimum CGPA for placement registration?
question> exit
```

Interactive mode initializes the expensive pipeline once and reuses it for every question.

### JSON output

```powershell
python ask.py "What changed?" --json
```

### Add or change documents

1. Put text-layer PDFs in `data/pdfs/`.
2. Stop the running process.
3. Start the application again.

The in-memory corpus is rebuilt when a new process starts.

---

## 7. Testing

### Compile all Python files

```powershell
$files = @(
  ".\ask.py",
  ".\verify_setup.py",
  ".\eval\run_eval.py"
) + (Get-ChildItem .\spitrag -Filter *.py | ForEach-Object { $_.FullName })

.\.venv\Scripts\python.exe -m py_compile $files
```

### Run the complete health check

```powershell
.\.venv\Scripts\python.exe verify_setup.py
```

This checks:

1. Groq API key exists.
2. Groq API is reachable.
3. PDFs are found.
4. Document metadata parses.
5. Clause chunks are built.
6. Embedding model loads.
7. Cross-encoder loads.
8. A real end-to-end question succeeds.

Expected result:

```text
8/8 checks passed
```

### Run the focused benchmark

```powershell
.\.venv\Scripts\python.exe .\eval\run_eval.py `
  --split test `
  --modes evidence_aware
```

Results are written to:

```text
eval/results/per_question.csv
```

---

## 8. Latest health-check results

| Check | Result |
|---|---|
| Groq key present | Passed |
| Groq API reachable | Passed |
| PDFs found with text layer | Passed: 20 |
| Document metadata parsed | Passed: 20 |
| Clause chunks built | Passed: 728 |
| Embedding model loads | Passed |
| Cross-encoder loads | Passed |
| End-to-end pipeline run | Passed |

Final result:

```text
8/8 checks passed
```

---

## 9. Focused evaluation results

The focused test split contained 13 questions.

| Metric | Result |
|---|---:|
| Answer accuracy | 30.8% |
| Recall@5 | 63.6% |
| Recall@10 | 63.6% |
| Citation support | 100% |
| Gold evidence cited | 80% |
| Abstention recall | 100% |
| Mean latency | 3,775.9 ms |

### What these results mean

The pipeline mechanics are working:

- It starts correctly.
- It retrieves passages.
- It generates answers.
- It verifies citations.
- It abstains when appropriate.

However, answer accuracy is only 30.8% in the current benchmark. This means the system is not ready to make unsupervised decisions for students.

The largest quality gaps are:

- Amended-policy questions
- Hinglish questions
- Typographical errors
- Retrieval recall
- Over-refusal on answerable questions
- Legacy benchmark questions that do not fully match the current corpus

LLM-generated amendments and answers may also vary between runs.

---

## 10. Safety behavior

The pipeline is designed to avoid unsupported answers.

- Unknown citation IDs are removed.
- Unsupported claims are removed in evidence-aware mode.
- Low-coverage questions abstain.
- Invalid amendment dates are rejected.
- Invalid amendment targets are rejected.
- Table-only amendments are matched to source text before acceptance.
- The source PDFs remain the authority.
- A valid amendment target can survive an unrelated invalid target.
- Secrets are not included in the report.

---

## 11. Known limitations

### OCR

Scanned PDFs are skipped. OCR is currently disabled.

### Latency

LLM calls are the main per-question cost after startup.

### Persistence

Indexes and embeddings are held in memory. A new process rebuilds them.

### Benchmark quality

The benchmark should be expanded and refreshed for:

- 2026-27 documents
- Circular amendments
- Date-specific behavior
- Admission batches
- Hinglish
- Typos
- Abstention cases

### Testing

The repository has health checks and evaluation, but should add automated unit tests for:

- Metadata parsing
- Clause inference
- JSON response parsing
- Date and batch applicability
- Amendment matching
- Abstention behavior

---

## 12. Recommended next steps

### Priority 1: Improve evaluation coverage

Create a benchmark aligned with the current PDFs and circulars.

### Priority 2: Improve retrieval

Tune retrieval for typos, Hinglish, clause references, and amendment subjects.

### Priority 3: Add unit tests

Test individual components without requiring the live API or transformer downloads.

### Priority 4: Add service hardening

Before deploying as a service, add:

- LLM timeouts
- Retry handling
- Structured logs
- Request metrics
- Rate limiting
- Health endpoints

### Priority 5: Add persistent indexing

Use a content hash of the PDF corpus to reuse indexes across processes and rebuild only when documents change.

---

## 13. Bottom line

The repository is technically functional and has strong citation verification and safe abstention behavior.

Use it now for:

- Research
- Demonstrations
- Supervised testing
- Pipeline development

Do not yet use it for:

- Unsupervised student decisions
- Official policy publication
- Production service-level guarantees

The next major goal is improving answer accuracy while preserving the current evidence and safety checks.
