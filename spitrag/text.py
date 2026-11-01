"""Tokenisation, query normalisation (language detection, Hinglish gloss, spell-fix)."""
import difflib
import re
from dataclasses import dataclass, field

STOP = set(
    "a an the is are was were be been of to in on for from by with and or if my i me can do does did what which who how "
    "when where why will would should shall may it its this that these those as at about into than then there their "
    "your you we our us not no any all each per via am have has had get got".split()
)
GENERIC = {"student", "students", "college", "spit", "institute", "please", "tell", "know", "want", "need", "give",
           "rule", "rules", "policy", "required", "require", "number", "many", "much", "sit", "appear",
           "whats", "hows", "happen", "happens", "found", "b", "tech", "btech", "de", "main", "ho", "ko", "ka", "ke",
           "se", "mein", "bhi", "toh", "to", "yeh", "woh", "kar", "kare", "ye", "wo"}
# light synonym folding so "exam" matches "examination", "calculated" matches "computation", etc.
SYN = {"examination": "exam", "examinations": "exam", "calculate": "comput", "calculated": "comput", "calculation": "comput",
       "computation": "comput", "computed": "comput", "compute": "comput", "evaluated": "evaluation", "reevaluation": "evaluation",
       "attendence": "attendance", "minimun": "minimum", "duration": "duration", "condone": "condonation", "condoned": "condonation",
       # month names and "sem" fold to the short forms the circulars use ("14-24 Dec 2026", "Sem I")
       "january": "jan", "february": "feb", "march": "mar", "april": "apr", "june": "jun", "july": "jul",
       "august": "aug", "september": "sep", "october": "oct", "november": "nov", "december": "dec", "sem": "semester"}

TOKEN_RE = re.compile(r"[a-z0-9ऀ-ॿ]+(?:\.[0-9]+)?")

# Tiny Hinglish / Hindi gloss: the English words are APPENDED to the query (expansion, not replacement).
GLOSS = {
    "kitna": "how much", "kitni": "how much", "kitne": "how many", "kya": "what", "kab": "when date",
    "sakta": "can eligible", "sakte": "can eligible", "nahi": "not", "paise": "fee",
    "mera": "my", "meri": "my", "pariksha": "exam", "hajiri": "attendance", "kam": "low shortage",
    "dobara": "re-exam retake", "ank": "marks", "tareekh": "date", "ki": "", "hai": "", "hu": "", "hoon": "",
    "उपस्थिति": "attendance", "परीक्षा": "exam", "शुल्क": "fee", "अंक": "marks", "तारीख": "date", "फीस": "fee",
}
HINGLISH_MARKERS = {"kya", "hai", "hu", "hoon", "kitna", "kitni", "kitne", "mera", "meri", "nahi", "sakta", "sakte",
                    "kab", "ki", "ka", "ke", "mein", "se", "pe", "paise", "dobara"}


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower().replace("–", " ").replace("—", " "))


def stem(t: str) -> str:
    if t in SYN:
        return SYN[t]
    if len(t) > 5 and t.endswith("ing"):
        return t[:-3]
    if len(t) > 4 and t.endswith("ed"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokens_stem(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text)]


def content_tokens(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text)
            if t not in STOP and t not in GENERIC and t not in GLOSS]


@dataclass
class NormalizedQuery:
    original: str
    language: str
    search_text: str
    fixes: list = field(default_factory=list)


def detect_language(q: str) -> str:
    deva = sum(1 for ch in q if "ऀ" <= ch <= "ॿ")
    if deva / max(1, len(q)) > 0.3:
        return "hi"
    toks = set(tokenize(q))
    if len(toks & HINGLISH_MARKERS) >= 1 and len(toks) >= 3:
        return "hinglish"
    return "en"


def normalize_query(q: str, vocab_list: list[str], vocab: set[str]) -> NormalizedQuery:
    toks = tokenize(q)
    out, fixes = [], []
    for t in toks:
        if t in vocab or t in GLOSS or len(t) <= 4 or any(ch.isdigit() for ch in t) or "ऀ" <= t[0] <= "ॿ":
            out.append(t)
            continue
        m = difflib.get_close_matches(t, vocab_list, n=1, cutoff=0.85)
        if m:
            out.append(m[0])
            fixes.append((t, m[0]))
        else:
            out.append(t)
    expansion = [GLOSS[t] for t in toks if GLOSS.get(t)]
    return NormalizedQuery(q, detect_language(q), " ".join(out + expansion), fixes)
