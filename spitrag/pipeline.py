"""Lane B: one pass per student question.

modes:
  vector          -> dense only
  hybrid          -> BM25 + dense
  hybrid_rerank   -> + cross-encoder
  evidence_aware  -> + version/authority/batch filtering, amendment handling, verification, abstention

Everything is built from the PDFs in DOCS_DIR when Pipeline() is constructed. No index or metadata files are read.
Scanned PDFs are skipped (OCR is disabled).
"""
import re
import sys
import time
from threading import Lock
from datetime import date

from . import amendments as amendments_mod, cache
from .amendments import attach_amendments, extract_amendments
from .config import ABSTAIN_MIN_COVERAGE, LLM_MODEL, MIN_QUERY_TERMS, TOP_K_CONTEXT
from .docmeta import build_documents
from .generate import best_excerpt, get_generator, unit_scores, units_of
from .ingest import build_chunks
from .pdf_source import load_all
from .retrieve import Retriever
from .text import content_tokens, normalize_query
from .verify import verify_claim
from .versions import D, amendment_index, amendments_for_chunk, applicability, is_batch_dependent

MODES = ["vector", "hybrid", "hybrid_rerank", "evidence_aware"]
CHANGE_WORDS = re.compile(r"\b(change[sd]?|differen\w*|compar\w*|previous|earlier|old|2024-25|what.s new|revised)\b", re.I)
_shared_pipeline = None
_shared_pipeline_lock = Lock()


def detect_batch(q: str):
    m = re.search(r"(?:batch|admitted|admission|joined)\D{0,12}(20\d\d)", q, re.I) or re.search(r"(20\d\d)\s*(?:batch|admission)", q, re.I)
    return m.group(1) if m else None


class Pipeline:
    def __init__(self):
        print("[pipeline] reading PDFs with text layers...", file=sys.stderr)
        self.pdfs = load_all()
        self.docs = build_documents(self.pdfs)
        self.chunks = build_chunks(self.pdfs, self.docs)
        self.by_id = {c["id"]: c for c in self.chunks}
        self.amendments = self._load_amendments()
        attach_amendments(self.chunks, self.amendments)
        self.amend_by_id = amendment_index(self.amendments)
        print(f"[pipeline] {len(self.docs)} documents, {len(self.chunks)} chunks, {len(self.amendments)} amendments",
              file=sys.stderr)
        self.retriever = Retriever(self.chunks)
        self.generator = get_generator()

    def _load_amendments(self):
        """Verified amendments from the cache, or extracted with the LLM (and cached) when any input changed."""
        key = cache.digest("amendments", cache.pdf_fingerprint(), LLM_MODEL, amendments_mod.PROMPT,
                           amendments_mod.RETRY, amendments_mod.FUZZY_MIN, sorted(self.docs.items()),
                           [(c["id"], c["clauses"]) for c in self.chunks])
        cached = cache.load_json("amendments", key)
        if cached is not None:
            return cached
        found = extract_amendments(self.docs, self.pdfs)
        if found or not any(d["doc_type"] == "circular" for d in self.docs.values()):
            cache.save_json("amendments", key, found)
        else:  # nothing kept although circulars exist: likely a bad LLM run, so don't pin it in the cache
            print("[pipeline] no amendments kept; not caching this result", file=sys.stderr)
        return found

    def _english_query(self, question: str):
        """LLM rewrite of a Hinglish/Hindi question into an English search query; None falls back to the gloss."""
        try:
            return self.generator.rewrite(question)
        except RuntimeError as e:
            print(f"[pipeline] query rewrite failed, using the gloss: {e}", file=sys.stderr)
            return None

    def _cite(self, chunk, claim_text=None):
        """Citation for a passage. The excerpt is the passage's own best-matching sentence(s) for the claim."""
        d = self.docs[chunk["doc_id"]]
        excerpt = (best_excerpt(chunk, claim_text, self.retriever.idf) if claim_text
                   else " ".join(units_of(chunk))[:300])
        return {"chunk_id": chunk["id"], "doc_id": chunk["doc_id"], "title": d["title"], "version": d["version"],
                "section": chunk["heading"], "clauses": chunk["clauses"], "pages": chunk["pages"],
                "published_on": d["published_on"], "effective_from": d["effective_from"], "excerpt": excerpt}

    def _abstain(self, out, reason, question):
        out.update(outcome="abstain", abstain_reason=reason, claims=[], claims_text="",
                   answer=("I could not find a reliable answer to this in the official documents I have, so I won't "
                           "guess. Please contact the relevant college office."))
        return out

    def ask(self, question: str, as_of=None, batch=None, mode: str = "evidence_aware") -> dict:
        t0 = time.perf_counter()
        as_of = D(as_of) if isinstance(as_of, str) else (as_of or date.today())
        batch = str(batch) if batch else detect_batch(question)
        nq = normalize_query(question, self.retriever.vocab_list, self.retriever.vocab)
        english_query = self._english_query(question) if nq.language in ("hinglish", "hi") else None
        if english_query:  # retrieval, coverage and generation all use the English rewrite
            nq_en = normalize_query(english_query, self.retriever.vocab_list, self.retriever.vocab)
            search_text, fixes = nq_en.search_text, nq_en.fixes
            terms = content_tokens(search_text)
        else:
            search_text, fixes = nq.search_text, nq.fixes
            terms = content_tokens(search_text)
            if nq.language != "en":  # untranslated Hinglish/Hindi words are not evidence the passages must contain
                terms = [t for t in terms if self.retriever.in_vocab(t)]
        question_en = english_query or question
        hits = self.retriever.search(search_text, mode)
        out = {"question": question, "mode": mode, "as_of": str(as_of), "batch": batch, "language": nq.language,
               "search_text": search_text, "english_query": english_query, "spell_fixes": fixes, "notices": [],
               "conflicts": [], "retrieved_ids": [self.chunks[i]["id"] for i, _ in hits], "abstain_reason": None,
               "embed_backend": self.retriever.dense.backend}

        if mode != "evidence_aware":  # baselines: no filtering, no verification
            ctx = [self.chunks[i] for i, _ in hits[:TOP_K_CONTEXT]]
            claims, _ = self.generator.generate(question_en, terms, ctx, as_of, batch)
            self._finish(out, claims, ctx, enforce=False)
            out["coverage"] = None
            out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            return out

        cand, amended, upcoming = [], [], {}
        considered = 0  # passages that would compete for the context; only these can raise a conflict or notice
        for i, _ in hits:
            c = self.chunks[i]
            if c["kind"] == "control" and not CHANGE_WORDS.search(question_en):
                continue
            doc = self.docs[c["doc_id"]]
            st = applicability(doc, c, as_of, batch, self.docs, self.amend_by_id)
            relevant = considered < TOP_K_CONTEXT
            if st == "not_yet_effective" and c.get("amend_ids") and relevant:
                for aid in c["amend_ids"]:
                    upcoming[aid] = self.amend_by_id[aid]
            if st != "current":
                continue
            considered += 1
            active, up = amendments_for_chunk(c, as_of, self.amendments)
            if relevant:
                for a, _ in up:
                    upcoming[a["id"]] = a
            if active:
                if relevant:  # an amended passage far down the ranking is not what the question is about
                    amended.append((c, active))
                continue
            cand.append(c)

        pulled = []
        for c, active in amended:
            a0, clause = active[0][0], active[0][1]
            out["conflicts"].append({
                "older_source": self._cite(c)["title"] + f" cl. {clause}", "older_says": " ".join(units_of(c))[:220],
                "newer_source": f"{a0['circular']} item {a0['item']}",
                "newer_says": "; ".join(a["summary"] for a, _ in active),
                "applies": f"newer (effective {a0['effective_from']}) as of {as_of}"})
            for a, _ in active:
                for cc in self.chunks:
                    if a["id"] in (cc.get("amend_ids") or []) and cc not in pulled and cc not in cand \
                            and applicability(self.docs[cc["doc_id"]], cc, as_of, batch, self.docs, self.amend_by_id) == "current":
                        pulled.append(cc)
        ctx = (pulled[:3] + cand)[:TOP_K_CONTEXT + 1]
        for a in upcoming.values():
            out["notices"].append(f"Upcoming change (effective {a['effective_from']}, {a['circular']} item {a['item']}): {a['summary']}")
        if batch is None and any(is_batch_dependent(c) for c in ctx):
            out["notices"].append("Batch not specified: the rules below assume the current 2026-27 admission batch. "
                                  "Earlier batches may follow the 2024-25 handbook.")

        out["context_ids"] = [c["id"] for c in ctx]
        best = unit_scores(terms, ctx, self.retriever.idf)
        out["coverage"] = round(max(best[0][0], 0.0), 3) if best else 0.0
        if len(set(terms)) < MIN_QUERY_TERMS:
            return self._finish_abstain(out, "clarification needed: question too short or ambiguous", question, t0)
        if not ctx:
            return self._finish_abstain(out, "no currently applicable evidence retrieved", question, t0)
        if out["coverage"] < ABSTAIN_MIN_COVERAGE:
            return self._finish_abstain(out, f"low evidence coverage ({out['coverage']})", question, t0)

        # Verified circular changes in force: the model is told which value replaced which, so it can't read the
        # circular's before/after table the wrong way round. Its claims are still checked against the passages.
        changes, seen = [], set()
        for _, active in amended:
            for a, _ in active:
                if a["id"] not in seen:
                    seen.add(a["id"])
                    changes.append(a)
        claims, insufficient = self.generator.generate(question_en, terms, ctx, as_of, batch, changes=changes)
        if insufficient or not claims:
            return self._finish_abstain(out, "generator found the evidence insufficient", question, t0)
        self._finish(out, claims, ctx, enforce=True)
        if out["outcome"] == "answer" and out["conflicts"]:
            out["outcome"] = "conflict"
        if out["outcome"] == "abstain":
            self._abstain(out, out["abstain_reason"], question)
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    def _finish_abstain(self, out, reason, question, t0):
        self._abstain(out, reason, question)
        out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    def _finish(self, out, claims, ctx, enforce):
        kept = []
        for cl in claims:
            passages = [self.by_id[e]["text"] for e in cl["evidence"] if e in self.by_id]
            ok, score = verify_claim(cl["text"], passages)
            cl.update(verified=ok, support_score=round(score, 2),
                      citations=[self._cite(self.by_id[e], cl["text"]) for e in cl["evidence"] if e in self.by_id])
            if ok or not enforce:
                kept.append(cl)
        out["n_claims"], out["n_verified"] = len(claims), sum(1 for c in claims if c["verified"])
        out["claims"] = kept
        out["claims_text"] = " ".join(c["text"] for c in kept)
        if not kept:
            out.update(outcome="abstain", abstain_reason="no claim passed citation verification")
            return
        lines = [f"- {c['text']} [{i}]" for i, c in enumerate(kept, 1)]
        out["answer"] = "\n".join(lines + [f"* {n}" for n in out["notices"]])
        out["outcome"] = "answer"


def get_pipeline() -> Pipeline:
    """Return the process-wide pipeline, initializing the expensive index once."""
    global _shared_pipeline
    if _shared_pipeline is None:
        with _shared_pipeline_lock:
            if _shared_pipeline is None:
                _shared_pipeline = Pipeline()
    return _shared_pipeline
