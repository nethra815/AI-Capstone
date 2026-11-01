"""Create a dependency-free PDF implementation and operations report."""
from pathlib import Path
import re
import textwrap


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SPIT_RAG_IMPLEMENTATION_REPORT.pdf"

REPORT = """
SPIT RAG
Implementation and Operations Guide
Generated 01 November 2026

READ THIS FIRST
Purpose: answer questions about the college regulation PDFs in data/pdfs/.
Current state: the pipeline runs end to end and verifies citations.
Important: benchmark answer quality is still experimental; see page 5.

AT A GLANCE
Corpus                         20 PDFs | 20 documents | 728 chunks
Health check                   8/8 checks passed
Verified amendments            9 in the final health-check run
Citation support               100% in the focused test split
Mean question latency          3,775.9 ms in the focused test split
Production readiness           Not yet; answer accuracy was 30.8%

1. WHAT THE SYSTEM DOES
The system answers a student question using official PDF evidence. It does
not search the open web and it does not rely on a pre-written answer database.
Every answer is built from the PDFs loaded at startup.

2. WHAT HAPPENS WHEN THE PIPELINE STARTS
Step 1  Read text-layer PDFs from data/pdfs/.
Step 2  Extract document ID, title, version, publication/effective dates,
        supersession, and batch information.
Step 3  Split documents into clause-level chunks with page references.
Step 4  Read circular amendments through the LLM.
Step 5  Validate amendment quotes, dates, target documents, and target clauses.
Step 6  Build BM25 and dense indexes and load the embedding/reranker models.

Startup is expensive. It should happen once per process, not once per question.
Use interactive mode or get_pipeline() to reuse the initialized pipeline.

3. WHAT HAPPENS FOR EACH QUESTION
Question
   |
   v
Normalize spelling/language and detect batch
   |
   v
Retrieve with BM25 + dense search
   |
   v
Rerank the best passages
   |
   v
Apply date, batch, version, and amendment rules
   |
   v
Send only selected evidence to the LLM
   |
   v
Verify every generated claim against cited source text
   |
   +--> Answer with citations
   +--> Conflict when an amendment changes an older rule
   +--> Abstain when evidence is weak or unsupported

4. MAIN FILES
ask.py
  User interface: one question, JSON output, or interactive mode.
verify_setup.py
  Eight-step environment, model, corpus, and end-to-end health check.
eval/run_eval.py
  Benchmark runner; writes eval/results/per_question.csv.
spitrag/pipeline.py
  Main application API: retrieval, policy filtering, generation, verification.
spitrag/pipeline.py:get_pipeline
  Thread-safe process-wide pipeline reuse.
spitrag/retrieve.py
  BM25, dense retrieval, and cross-encoder reranking.
spitrag/amendments.py
  Circular extraction and safety validation.
spitrag/llm.py
  Schema-aware JSON response parsing.

5. INSTALLATION
Run these commands from the project directory:

  python -m venv .venv
  .venv\\Scripts\\activate
  pip install -r requirements.txt

Create a local .env file and set:

  GROQ_API_KEY=your-key

Optional settings include SPIT_LLM_MODEL, SPIT_DOCS_DIR,
SPIT_EMBED_MODEL, SPIT_RERANK_MODEL, and SPIT_ABSTAIN_COVERAGE.
Never put secrets in source code. The .env file is ignored by git and is not
included in this report.

6. HOW TO USE
One question:
  python ask.py "What is the minimum attendance required in each course?"

With policy date and admission batch:
  python ask.py "What is the condonation fee?" --as-of 2026-11-01 --batch 2025

Multiple questions, efficient mode:
  python ask.py --interactive
  Type a question at question> and type exit to stop.

Machine-readable output:
  python ask.py "What changed?" --json

Adding or changing PDFs:
  Put text-layer PDFs into data/pdfs/ and restart the process.
  Scanned PDFs are skipped because OCR is disabled.

7. TESTING
Compile all Python files:
  python -m py_compile ask.py verify_setup.py spitrag\\*.py eval\\run_eval.py

Run the complete health check:
  python verify_setup.py
  Expected result: 8/8 checks passed.

Run the focused benchmark:
  python eval\\run_eval.py --split test --modes evidence_aware
  Results: eval/results/per_question.csv

8. VERIFIED HEALTH RESULTS
Check                         Result
Python compilation            Passed
Groq API reachability         Passed
PDF loading                   Passed: 20 PDFs
Metadata parsing              Passed: 20 documents
Chunk construction            Passed: 728 chunks
Embedding model               Passed
Cross-encoder                 Passed
End-to-end question           Passed

9. QUALITY RESULTS AND MEANING
The focused test split contained 13 questions:

Metric                        Result
Answer accuracy               30.8%
Recall@5                      63.6%
Recall@10                     63.6%
Citation support              100%
Gold evidence cited           80%
Abstention recall             100%
Mean latency                  3,775.9 ms

Interpretation:
The engineering pipeline is functioning: it starts, retrieves evidence,
answers, cites, and abstains safely. However, 30.8% answer accuracy means
the system must not yet be presented as production-ready. The benchmark is
small and includes difficult amended-policy, Hinglish, typo, and stale-policy
questions. Results may also vary slightly because amendment extraction and
answer generation use an LLM.

10. SAFETY AND CORRECTNESS RULES
- Unknown citation IDs are removed.
- Unsupported claims are removed in evidence-aware mode.
- Low-coverage questions abstain instead of guessing.
- Invalid amendment dates and targets are rejected.
- Table-only circular amendments may be matched to a target clause using
  before/after values; a clause is never accepted without source verification.
- An amendment with one valid target can survive an unrelated invalid target.
- The source PDFs remain the authority.

11. RECOMMENDED NEXT WORK
Priority 1  Refresh and expand the benchmark for the current 2026-27 PDFs.
Priority 2  Improve retrieval for Hinglish, typos, and amended rules.
Priority 3  Add unit tests for metadata, JSON parsing, clause inference,
            applicability, and abstention.
Priority 4  Add LLM timeouts, retries, structured logs, and request metrics.
Priority 5  Add a content-hashed persistent index for multi-process serving.

BOTTOM LINE
Use the system now for research, demos, and supervised testing. It has strong
citation verification and safe abstention behavior. Improve benchmark accuracy
and add service hardening before using it for unsupervised student decisions.
"""


def pdf_escape(value: str) -> str:
    value = value.encode("ascii", "replace").decode("ascii")
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def lines_for_report(text: str) -> list[str]:
    result = []
    for raw in text.strip().splitlines():
        if not raw.strip():
            result.append("")
        else:
            result.extend(textwrap.wrap(raw, width=88, break_long_words=False) or [""])
    return result


def make_pdf(lines: list[str]) -> bytes:
    per_page = 46
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)]
    objects = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    bold_font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    page_ids = []
    content_ids = []
    for page_lines in pages:
        commands = ["BT", "/F1 9 Tf", "50 790 Td", "13 TL"]
        for line in page_lines:
            stripped = line.strip()
            if stripped and (re.match(r"^\d+\.", stripped) or stripped in {
                    "READ THIS FIRST", "AT A GLANCE", "BOTTOM LINE"}):
                commands.extend(["0 0 0 rg", "/F2 12 Tf", f"({pdf_escape(stripped)}) Tj",
                                 "/F1 9 Tf", "0 -1.2 Td"])
            elif stripped and stripped.isupper() and len(stripped) < 70:
                commands.extend(["/F2 10 Tf", f"({pdf_escape(stripped)}) Tj", "/F1 9 Tf"])
            else:
                commands.append(f"({pdf_escape(line)}) Tj")
            commands.append("0 -1 Td")
        commands.append("ET")
        commands.extend(["BT", "/F1 8 Tf", "50 25 Td",
                         f"(SPIT RAG | Page {pages.index(page_lines) + 1} of {len(pages)}) Tj", "ET"])
        content = ("\n".join(commands)).encode("ascii")
        content_ids.append(add(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n"
                               + content + b"\nendstream"))
        page_ids.append(add(b""))
    pages_id = add(b"")
    for page_id, content_id in zip(page_ids, content_ids):
        objects[page_id - 1] = (
            b"<< /Type /Page /Parent " + str(pages_id).encode() + b" 0 R "
            b"/MediaBox [0 0 595 842] /Resources << /Font << /F1 "
            + str(font_id).encode() + b" 0 R /F2 " + str(bold_font_id).encode()
            + b" 0 R >> >> /Contents "
            + str(content_id).encode() + b" 0 R >>"
        )
    kids = b" ".join(str(page_id).encode() + b" 0 R" for page_id in page_ids)
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_ids)).encode() + b" >>"
    catalog_id = add(b"<< /Type /Catalog /Pages " + str(pages_id).encode() + b" 0 R >>")

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
                  f"startxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


if __name__ == "__main__":
    OUTPUT.write_bytes(make_pdf(lines_for_report(REPORT)))
    print(OUTPUT)
