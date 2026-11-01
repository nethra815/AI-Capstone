"""HTTP API around the SPIT RAG pipeline. Run: uvicorn api.main:app --reload --port 8000

The pipeline is built once, in a background thread, so the server answers /api/health immediately while models load.
Nothing in spitrag/ is changed here; this module only wraps it.
"""
import csv
import json
import re
import sys
import threading
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from spitrag.config import DOCS_DIR, ROOT
from spitrag.pipeline import MODES, get_pipeline

FEEDBACK_FILE = ROOT / "data" / "feedback.jsonl"
EVAL_FILE = ROOT / "eval" / "results" / "per_question.csv"


class _State:
    pipeline = None
    error: Optional[str] = None
    started = time.time()
    ready_after: Optional[float] = None
    llm_failures = 0
    asks = 0


state = _State()
_feedback_lock = threading.Lock()


def _build_pipeline():
    try:
        state.pipeline = get_pipeline()
        state.ready_after = round(time.time() - state.started, 1)
    except SystemExit as e:  # spitrag raises SystemExit for missing key / missing PDFs
        state.error = str(e)
    except Exception as e:  # noqa: BLE001 - surface any startup failure through /api/health
        state.error = f"{type(e).__name__}: {e}"
    if state.error:
        print(f"[api] pipeline failed to start: {state.error}", file=sys.stderr)


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_build_pipeline, name="pipeline-init", daemon=True).start()
    yield


app = FastAPI(title="SPIT Campus Assistant API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _error(status: int, code: str, message: str):
    return JSONResponse({"error": code, "message": message}, status_code=status)


def _not_ready():
    if state.error:
        return _error(500, "pipeline_failed", f"The assistant could not start: {state.error}")
    return _error(503, "loading", "The assistant is still loading the official documents. Please try again shortly.")


# ---------- health ----------

@app.get("/api/health")
def health():
    p = state.pipeline
    out = {"ready": p is not None, "documents": len(p.docs) if p else 0, "chunks": len(p.chunks) if p else 0,
           "amendments": len(p.amendments) if p else 0,
           "loading_seconds": None if p else round(time.time() - state.started, 1),
           "asks": state.asks, "llm_failures": state.llm_failures}
    if state.error:
        out["error"] = state.error
    return out


# ---------- ask ----------

class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    as_of: Optional[str] = None
    batch: Optional[str] = None
    mode: Literal["vector", "hybrid", "hybrid_rerank", "evidence_aware"] = "evidence_aware"

    @field_validator("question")
    @classmethod
    def _strip(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("question is empty")
        return v

    @field_validator("as_of")
    @classmethod
    def _date(cls, v):
        if v in (None, ""):
            return None
        date.fromisoformat(v)  # raises ValueError -> 422
        return v

    @field_validator("batch")
    @classmethod
    def _batch(cls, v):
        if v in (None, "", "auto"):
            return None
        if not re.fullmatch(r"20\d\d", v):
            raise ValueError("batch must be a year such as 2025")
        return v


@app.post("/api/ask")
def ask(body: AskBody):
    if state.pipeline is None:
        return _not_ready()
    state.asks += 1
    try:
        return state.pipeline.ask(body.question, as_of=body.as_of, batch=body.batch, mode=body.mode)
    except SystemExit as e:  # GROQ_API_KEY missing
        return _error(500, "llm_not_configured", f"The language model is not configured on the server: {e}")
    except RuntimeError as e:  # e.g. "LLM returned no JSON"
        state.llm_failures += 1
        print(f"[api] LLM failure #{state.llm_failures} of {state.asks} asks: {e}", file=sys.stderr)
        return _error(502, "llm_failed", "The language model did not return a usable answer. Please try again.")
    except Exception as e:  # noqa: BLE001 - network errors from the LLM client etc.
        state.llm_failures += 1
        print(f"[api] ask failed: {type(e).__name__}: {e}", file=sys.stderr)
        return _error(500, "ask_failed", "Something went wrong while checking the documents. Please try again.")


# ---------- documents ----------

TOPICS = [  # (topic, keywords matched against doc id + file name, lower-cased)
    ("Attendance", ("attendance", "-att-", "-cnd-")),
    ("Academic regulations", ("/arh/", "/gcp/", "academic", "grading")),
    ("Examinations", ("exam", "-exm-")),
    ("Fees and scholarships", ("/acc/", "fee", "/sch/", "scholarship")),
    ("Placement", ("/plc/", "placement")),
    ("Hostel", ("-hst-", "hostel")),
    ("Library", ("-lib-", "library")),
    ("Student life", ("-clb-", "club")),
    ("Conduct and grievances", ("-coc-", "-grv-", "conduct", "grievance")),
]
GENERIC_TITLES = {"sardar patel institute of technology (spit)"}


def _topic(d):
    key = f"{d['doc_id']} {d['file']}".lower()
    return next((t for t, kws in TOPICS if any(k in key for k in kws)), "Other")


def _display_title(d):
    """The PDFs put different things in the first line; pick a human-readable name."""
    title = (d.get("title") or "").strip()
    if "|" in title:
        parts = [p.strip() for p in title.split("|")]
        named = [p for p in parts[1:] if len(p.split()) >= 2 and p[:1].isalpha() and not re.match(r"(version|page)\b", p, re.I)
                 and re.search(r"[a-z]{3}", p)]
        if named:
            return named[0]
    elif title and title.lower() not in GENERIC_TITLES:
        return title
    name = Path(d["file"]).stem
    name = re.sub(r"^\d+_", "", name)
    name = re.sub(r"^[A-Z]+(?:-[A-Z0-9]+)+-\d{3}\s+", "", name)  # leading document id
    name = re.sub(r"[_ ]old$", "", name).replace("_", " ").strip()
    return name.title() if name.islower() else name


def _is_circular(d, display):
    return d["doc_type"] == "circular" or "circular" in display.lower() or "amendment" in (d.get("title") or "").lower()


def _status(d, circular, today):
    ef = date.fromisoformat(d["effective_from"]) if d["effective_from"] else None
    et = date.fromisoformat(d["effective_to"]) if d["effective_to"] else None
    if et and today > et:
        return "superseded"
    if ef and today < ef:
        return "upcoming"
    return "circular" if circular else "current"


_doc_cache = None


def _documents():
    """Documents enriched with display fields. Cached: the corpus is fixed for the life of the process."""
    global _doc_cache
    if _doc_cache is not None:
        return _doc_cache
    p = state.pipeline
    text_by_file = {pdf["file"]: "\n".join(pdf["pages"]) for pdf in p.pdfs}
    targets = defaultdict(set)
    for a in p.amendments:
        circ = a.get("circular") or a["id"].split("#")[0]
        for t in a.get("targets", []):
            if t.get("doc_id"):
                targets[circ].add(t["doc_id"])
    today = date.today()
    rows = []
    for d in p.docs.values():
        display = _display_title(d)
        circular = _is_circular(d, display)
        amends = set(targets.get(d["doc_id"], set()))
        if circular:  # a circular names the documents it amends in its own text
            text = text_by_file.get(d["file"], "")
            amends |= {o for o in p.docs if o != d["doc_id"] and o in text and not p.docs[o]["superseded_by"]}
        rows.append({
            "id": d["doc_id"], "title": d["title"], "display_title": display, "topic": _topic(d),
            "version": d["version"], "doc_type": "circular" if circular else d["doc_type"],
            "published_on": d["published_on"], "effective_from": d["effective_from"],
            "effective_to": d["effective_to"], "supersedes": d["supersedes"], "superseded_by": d["superseded_by"],
            "amends": sorted(amends), "status": _status(d, circular, today),
            "n_pages": d["n_pages"], "file": d["file"],
        })
    rows.sort(key=lambda r: ([t for t, _ in TOPICS].index(r["topic"]) if r["topic"] != "Other" else 99,
                             r["effective_from"] or "", r["id"]))
    _doc_cache = rows
    return rows


@app.get("/api/documents")
def documents():
    if state.pipeline is None:
        return _not_ready()
    return _documents()


@app.get("/api/documents/{doc_id:path}/pdf")
def document_pdf(doc_id: str):
    if state.pipeline is None:
        return _not_ready()
    d = state.pipeline.docs.get(doc_id)
    if not d:
        return _error(404, "not_found", "No document with that ID.")
    base = Path(DOCS_DIR).resolve()
    path = (base / d["file"]).resolve()
    if not path.is_relative_to(base) or not path.is_file() or path.suffix.lower() != ".pdf":
        return _error(404, "not_found", "The PDF for this document is not available.")
    return FileResponse(path, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{path.name}"'})


# ---------- feedback ----------

class FeedbackBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    outcome: Literal["answer", "conflict", "abstain", "error"]
    helpful: bool
    comment: Optional[str] = Field(default=None, max_length=1000)


@app.post("/api/feedback")
def feedback(body: FeedbackBody):
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **body.model_dump()}
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _feedback_lock, FEEDBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": True}


# ---------- evaluation summary ----------

def _b(v):
    return {"True": True, "False": False}.get(v)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


@app.get("/api/eval")
def eval_summary():
    if not EVAL_FILE.is_file():
        return {"available": False, "modes": [], "categories": []}
    with EVAL_FILE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_mode = defaultdict(list)
    for r in rows:
        by_mode[r["mode"]].append(r)
    modes = []
    for mode in [m for m in MODES if m in by_mode] + [m for m in by_mode if m not in MODES]:
        rs = by_mode[mode]
        answerable = [r for r in rs if not _b(r["should_abstain"])]
        unanswerable = [r for r in rs if _b(r["should_abstain"])]
        cv = [json.loads(r["cit_verified"]) for r in rs if r.get("cit_verified")]
        claims = sum(c[1] for c in cv)
        modes.append({
            "mode": mode, "n": len(rs),
            "accuracy": _mean([_b(r["correct"]) for r in rs]),
            "abstention_rate": _mean([_b(r["abstained"]) for r in rs]),
            "abstention_recall": _mean([_b(r["abstained"]) for r in unanswerable]),
            "over_refusal": _mean([_b(r["over_refusal"]) for r in answerable]),
            "stale_errors": sum(1 for r in rs if _b(r["stale_error"])),
            "citation_verified": round(sum(c[0] for c in cv) / claims, 4) if claims else None,
            "recall_at_5": _mean([_b(r["recall@5"]) for r in rs]),
            "avg_latency_ms": round(_mean([float(r["latency_ms"]) for r in rs if r["latency_ms"]]) or 0, 1),
        })
    cats = defaultdict(lambda: defaultdict(list))
    for r in rows:
        cats[r["category"]][r["mode"]].append(_b(r["correct"]))
    categories = [{"category": c, "n": max(len(v) for v in m.values()),
                   "accuracy": {mode: _mean(v) for mode, v in m.items()}} for c, m in cats.items()]
    return {"available": True, "n_questions": len({r["id"] for r in rows}), "modes": modes,
            "categories": categories,
            "updated": datetime.fromtimestamp(EVAL_FILE.stat().st_mtime, timezone.utc).date().isoformat()}
