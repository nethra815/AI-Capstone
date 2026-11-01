"""Claim-level citation verification (Phase-1 heuristic).

A claim is SUPPORTED if, for at least one cited passage, (a) every number in the claim also appears in the passage
and (b) enough of the claim's content words appear in the passage. Swap in an NLI model or LLM judge later by
replacing `verify_claim` - the pipeline only depends on its return value.
"""
import re

from .config import SUPPORT_MIN_RECALL
from .text import content_tokens, tokens_stem

NUM = re.compile(r"\d+(?:\.\d+)?")


def _nums(s: str) -> set[str]:
    return set(NUM.findall(re.sub(r"(?<=\d),(?=\d{3})", "", s)))


def verify_claim(claim_text: str, passages: list[str]) -> tuple[bool, float]:
    ct = set(content_tokens(claim_text))
    cn = _nums(claim_text)
    best = 0.0
    for p in passages:
        recall = len(ct & set(tokens_stem(p))) / max(1, len(ct))
        best = max(best, recall)
        if cn <= _nums(p) and recall >= SUPPORT_MIN_RECALL:
            return True, recall
    return False, best
