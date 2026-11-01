"""Answer generation through Groq. Returns claims that each cite passage ids from the evidence.

The model must return JSON. Claims citing unknown ids are dropped; the verifier in verify.py then checks the rest.
"""
import re

from .llm import chat_json
from .text import tokens_stem


def _cells(line):
    return [re.sub(r"\*\*", "", c).strip() for c in line.strip().strip("|").split("|")]


def units_of(chunk: dict) -> list[str]:
    out = []
    for line in chunk["text"].splitlines():
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z₹0-9])", line):
            if len(s.split()) >= 3:
                out.append(s.strip())
    return out


def unit_scores(terms, context, idf):
    """IDF-weighted share of the query's content terms covered by each sentence. Also the evidence-coverage signal."""
    qt = {t for t in terms if not t.replace(".", "").isdigit()}
    total = sum(idf(t) for t in qt) or 1.0
    out = []
    for rank, ch in enumerate(context):
        cx = set(tokens_stem(f"{ch['heading']} {' '.join(ch['clauses'])}"))
        for u in units_of(ch):
            ut = set(tokens_stem(u))
            s = (sum(idf(t) for t in qt & ut) + 0.5 * sum(idf(t) for t in (qt & cx) - ut)) / total
            out.append((s - 0.005 * rank, u, ch["id"]))
    return sorted(out, key=lambda x: -x[0])


SYSTEM = """You answer student questions about college regulations using ONLY the evidence passages provided.
Rules: (1) every factual claim must cite the passage ids that support it; (2) never add a rule, number or date that is
not in the passages; (3) evidence marked CURRENT is the applicable rule on the given date; (4) if the passages do not
answer the question, set "insufficient" to true and return no claims.
Reply with JSON only: {"claims":[{"text":"...","evidence":["<id>"]}],"insufficient":false}"""


class LLMGenerator:
    def generate(self, question, query_terms, context, as_of=None, batch=None):
        ev = "\n\n".join(f"[{c['id']}] {c['title']} v{c['version']} - {c['heading']}\n{c['text']}" for c in context)
        data = chat_json(SYSTEM, f"Policies apply as of: {as_of}. Student batch: {batch or 'unknown'}.\n\n"
                                 f"EVIDENCE:\n{ev}\n\nQUESTION: {question}", required_key="claims")
        valid = {c["id"] for c in context}
        claims = [{"text": c["text"], "evidence": [e for e in c.get("evidence", []) if e in valid]}
                  for c in data.get("claims", []) if c.get("text")]
        return claims, bool(data.get("insufficient", not claims))


def get_generator():
    return LLMGenerator()
