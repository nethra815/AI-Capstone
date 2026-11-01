"""Run this before using the bot. It checks each piece and prints PASS/FAIL with the reason.

    # put GROQ_API_KEY=... in a .env file at the project root (see .env.example)
    python verify_setup.py
"""
import os
import sys

from spitrag.config import DOCS_DIR, EMBED_MODEL, LLM_MODEL, RERANK_MODEL, GROQ_API_KEY, GROQ_BASE_URL

results = []


def check(name, fn):
    try:
        detail = fn()
        results.append(True)
        print(f"PASS  {name}" + (f"  ({detail})" if detail else ""))
    except SystemExit as e:
        results.append(False)
        print(f"FAIL  {name}  -> {e}")
    except Exception as e:  # noqa: BLE001
        results.append(False)
        print(f"FAIL  {name}  -> {type(e).__name__}: {e}")


def c_key():
    if not GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY not set: add it to .env (copy .env.example)")
    return "set, loaded from .env or environment"


def c_api():
    from openai import OpenAI
    r = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL).chat.completions.create(
        model=LLM_MODEL, max_tokens=5, messages=[{"role": "user", "content": "Reply with OK"}])
    return f"model {LLM_MODEL} replied: {(r.choices[0].message.content or '').strip()[:20]!r}"


def c_pdfs():
    from spitrag.pdf_source import load_all
    pdfs = load_all(DOCS_DIR)
    return f"{len(pdfs)} text-layer PDFs in {DOCS_DIR}"


def c_docs():
    from spitrag.pdf_source import load_all
    from spitrag.docmeta import build_documents
    docs = build_documents(load_all(DOCS_DIR))
    missing = [d["file"] for d in docs.values() if not d["effective_from"]]
    if missing:
        print(f"      note: no effective date found in {missing}; they apply at any date")
    return f"{len(docs)} documents parsed"


def c_chunks():
    from spitrag.pdf_source import load_all
    from spitrag.docmeta import build_documents
    from spitrag.ingest import build_chunks
    pdfs = load_all(DOCS_DIR)
    chunks = build_chunks(pdfs, build_documents(pdfs))
    if len(chunks) < 10:
        raise SystemExit("too few chunks; check the PDFs have readable text")
    return f"{len(chunks)} clause-level chunks"


def c_embed():
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(EMBED_MODEL)
    return f"{EMBED_MODEL} dim={m.encode(['test']).shape[1]}"


def c_rerank():
    from sentence_transformers import CrossEncoder
    CrossEncoder(RERANK_MODEL).predict([("q", "d")])
    return RERANK_MODEL


def c_end_to_end():
    from spitrag.pipeline import Pipeline
    p = Pipeline()
    q = "What documents are in the corpus about attendance?"
    res = p.ask(q, mode="hybrid_rerank")
    if not res.get("retrieved_ids"):
        raise SystemExit("retrieval returned nothing")
    return f"ask() returned outcome={res['outcome']}, {len(res['retrieved_ids'])} chunks retrieved"


for name, fn in [("Groq key present", c_key), ("Groq API reachable", c_api), ("PDFs found with text layer", c_pdfs),
                 ("Document metadata parsed", c_docs), ("Clause chunks built", c_chunks),
                 ("Embedding model loads", c_embed), ("Cross-encoder loads", c_rerank),
                 ("End-to-end pipeline run", c_end_to_end)]:
    check(name, fn)
print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
