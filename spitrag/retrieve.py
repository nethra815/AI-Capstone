"""Hybrid retrieval: BM25 + dense embeddings (sentence-transformers) fused with RRF, then cross-encoder rerank."""
import math

import numpy as np
from rank_bm25 import BM25Okapi

from .config import EMBED_MODEL, RERANK_MODEL, RRF_K, TOP_K_RETRIEVE
from .text import tokenize, tokens_stem


class Retriever:
    def __init__(self, chunks):
        from sentence_transformers import CrossEncoder, SentenceTransformer
        self.chunks = chunks
        stems = [tokens_stem(c["index_text"]) for c in chunks]
        self.bm25 = BM25Okapi(stems)
        raw = {t for c in chunks for t in tokenize(c["index_text"])}
        self.vocab, self.vocab_list = raw, sorted(raw)
        self.embedder = SentenceTransformer(EMBED_MODEL)
        self.emb = self.embedder.encode([c["index_text"] for c in chunks], normalize_embeddings=True,
                                        batch_size=32, show_progress_bar=False)
        self.reranker = CrossEncoder(RERANK_MODEL)
        self.dense = type("D", (), {"backend": f"sentence-transformers:{EMBED_MODEL}"})()
        self.chunk_stems = [set(s) for s in stems]
        n = len(chunks)
        df = {}
        for s in self.chunk_stems:
            for t in s:
                df[t] = df.get(t, 0) + 1
        self._idf = {t: math.log((n + 1) / (d + 0.5)) for t, d in df.items()}
        self._max_idf = max(self._idf.values())

    def rerank_available(self) -> bool:
        return self.reranker is not None

    def idf(self, t):  # out-of-vocabulary terms count as maximally informative
        return self._idf.get(t, self._max_idf)

    def in_vocab(self, stemmed_term: str) -> bool:
        return stemmed_term in self._idf

    def _dense_scores(self, query: str) -> np.ndarray:
        return self.emb @ self.embedder.encode([query], normalize_embeddings=True)[0]

    def search(self, query: str, mode: str = "hybrid_rerank", k: int = TOP_K_RETRIEVE):
        dn = self._dense_scores(query)
        if mode == "vector":
            order = list(np.argsort(-dn)[:k])
            return [(int(i), float(dn[i])) for i in order]
        bm = self.bm25.get_scores(tokens_stem(query))
        rank = {}
        for scores in (bm, dn):
            for r, i in enumerate(np.argsort(-scores)[:50]):
                rank[int(i)] = rank.get(int(i), 0.0) + 1.0 / (RRF_K + r + 1)
        fused = sorted(rank, key=lambda i: -rank[i])[:k]
        if mode in ("hybrid_rerank", "evidence_aware"):
            sc = self.reranker.predict([(query, self.chunks[i]["index_text"]) for i in fused])
            fused = [i for _, i in sorted(zip(sc, fused), key=lambda x: -x[0])]
        return [(i, rank[i]) for i in fused]
