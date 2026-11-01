"""Answer generation through Groq. Returns claims that each cite passage ids from the evidence.

The model must return JSON. Claims citing unknown ids are dropped; the verifier in verify.py then checks the rest.
"""
import re

from .llm import chat_json
from .text import content_tokens, tokens_stem


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
answer the question, set "insufficient" to true and return no claims; (5) if CHANGES IN FORCE are listed, the earlier
provision no longer applies: state the revised provision and cite the passage that states it; (6) copy numbers, amounts
and dates exactly as the passage writes them. Write every claim in English, even if the question is Hindi or Hinglish.
Reply with JSON only: {"claims":[{"text":"...","evidence":["<id>"]}],"insufficient":false}"""

REWRITE = """Rewrite the student's question, which is in Hinglish or Hindi, as one short English search query about
college rules. Keep every specific detail (numbers, years, course, document or office names). Do not answer it and do
not add facts. Reply with JSON only: {"query":"<English query>"}"""


def best_excerpt(chunk: dict, claim_text: str, idf, limit: int = 300) -> str:
    """The sentence(s) of the source passage that best support a claim, in their original order."""
    flat = re.sub(r"\s+", " ", evidence_text(chunk)).strip()
    sentences = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z₹0-9(])", flat) if s]
    pseudo = {"id": chunk["id"], "heading": "", "clauses": [], "text": "\n".join(sentences)}
    scored = [s for s in unit_scores(content_tokens(claim_text), [pseudo], idf) if s[0] > 0]
    if not scored:
        return flat[:limit]
    picked = [scored[0][1]]
    if len(picked[0]) < 120 and len(scored) > 1:  # a short best sentence gets its runner-up for context
        picked.append(scored[1][1])
    picked.sort(key=flat.find)
    return " ".join(picked)[:limit]


def changes_block(changes, as_of) -> str:
    """Verified circular amendments in force on the policy date, as plain lines for the prompt."""
    if not changes:
        return ""
    lines = [f"- {a.get('subject')}: earlier provision {a.get('old_value')!r}; revised provision {a.get('new_value')!r}; "
             f"in force from {a['effective_from']} ({a['circular']} item {a['item']})" for a in changes]
    return f"CHANGES IN FORCE on {as_of} (verified from circulars):\n" + "\n".join(lines) + "\n\n"


# Page furniture repeated on every page of the PDFs. It carries no rule, so it is not sent to the model.
BOILERPLATE = re.compile(r"SYNTHETIC\b.*\bRESEARCH|^\S+\s+\|\s+.*\|\s+(?:Page|Version)\b|^Page\s+\d+(?:\s+of\s+\d+)?$",
                         re.I)


def evidence_text(chunk: dict) -> str:
    """The chunk's text without page headers, footers and its own document-id line."""
    lines = [l for l in chunk["text"].splitlines()
             if l.strip() and l.strip() != chunk["doc_id"] and not BOILERPLATE.search(l.strip())]
    return "\n".join(lines)


def evidence_block(context) -> str:
    """One block per distinct passage: a passage whose text was already sent is not sent again."""
    seen, blocks = set(), []
    for c in context:
        text = evidence_text(c)
        key = re.sub(r"\s+", " ", text).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        blocks.append(f"[{c['id']}] {c['title']} v{c['version']} - {c['heading']}\n{text}")
    return "\n\n".join(blocks)


class LLMGenerator:
    def generate(self, question, query_terms, context, as_of=None, batch=None, changes=None):
        # gpt-oss is a reasoning model: its hidden reasoning counts against max_tokens, so leave room for it.
        data = chat_json(SYSTEM, f"Policies apply as of: {as_of}. Student batch: {batch or 'unknown'}.\n\n"
                                 f"{changes_block(changes, as_of)}EVIDENCE:\n{evidence_block(context)}\n\n"
                                 f"QUESTION: {question}",
                         required_key="claims", max_tokens=2000, temperature=0, reasoning_effort="low")
        valid = {c["id"] for c in context}
        claims = [{"text": c["text"], "evidence": [e for e in c.get("evidence", []) if e in valid]}
                  for c in data.get("claims", []) if c.get("text")]
        return claims, bool(data.get("insufficient", not claims))

    def rewrite(self, question: str) -> str | None:
        """English search query for a Hinglish or Hindi question, or None if the model gives nothing usable."""
        data = chat_json(REWRITE, question, max_tokens=400, required_key="query", temperature=0, reasoning_effort="low")
        query = re.sub(r"\s+", " ", str(data.get("query") or "")).strip()
        return query[:200] or None


def get_generator():
    return LLMGenerator()
