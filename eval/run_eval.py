"""Phase-1 evaluation: four systems, one benchmark.

    python eval/run_eval.py                 # all 4 modes, all questions
    python eval/run_eval.py --split test    # report on the held-out half
    python eval/run_eval.py --sweep         # abstention-threshold sweep on the dev half
    python eval/run_eval.py -v              # show per-question failures
    python eval/run_eval.py --benchmark eval/regression.jsonl --out eval/results/regression_x.csv --pace 16
                                            # another question set, its own results file, paced for rate limits
"""
import argparse
import csv
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from spitrag.pipeline import MODES, get_pipeline  # noqa: E402

HERE = Path(__file__).resolve().parent

# Token meter: counts usage on every chat completion, whatever spitrag does internally.
TOKENS = {"calls": 0, "prompt": 0, "completion": 0, "total": 0, "truncated": 0}


def _install_token_meter():
    from openai.resources.chat.completions import Completions
    original = Completions.create

    def create(self, *args, **kwargs):
        r = original(self, *args, **kwargs)
        TOKENS["calls"] += 1
        if getattr(r, "usage", None):
            TOKENS["prompt"] += r.usage.prompt_tokens or 0
            TOKENS["completion"] += r.usage.completion_tokens or 0
            TOKENS["total"] += r.usage.total_tokens or 0
        if r.choices and r.choices[0].finish_reason == "length":
            TOKENS["truncated"] += 1
        return r
    Completions.create = create


def _error_result(reason):
    return {"outcome": "error", "claims": [], "claims_text": "", "retrieved_ids": [], "latency_ms": 0,
            "abstain_reason": f"error: {reason[:80]}", "language": None}


def _ask(pipe, q, mode):
    """pipe.ask with a wait-and-retry on provider rate limits. Other failures become an 'error' outcome."""
    from openai import RateLimitError
    for _ in range(4):
        try:
            return pipe.ask(q["question"], as_of=q["as_of"], batch=q.get("batch"), mode=mode)
        except RateLimitError as e:
            m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(e))
            wait = (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else 20
            print(f"  rate limited, waiting {wait:.0f}s", file=sys.stderr)
            time.sleep(wait + 1)
        except (RuntimeError, SystemExit) as e:
            print(f"  [ERROR {q['id']} {mode}] {e}", file=sys.stderr)
            return _error_result(str(e))
    return _error_result("rate limited")


def norm(s: str) -> str:
    s = s.lower().replace("**", "").replace("–", "-").replace("—", "-")
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    return re.sub(r"\s+", " ", s)


def load_benchmark(split, path=None):
    path = Path(path) if path else HERE / "benchmark.jsonl"
    qs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for i, q in enumerate(qs):
        q["split"] = "dev" if i % 2 == 0 else "test"
    return [q for q in qs if split == "all" or q["split"] == split]


def gold_hit(chunk, g):
    return (not g.get("doc") or chunk["doc_id"] == g["doc"]) and norm(g["contains"]) in norm(chunk["text"])


def judge(q, res):
    """Returns dict of per-question booleans."""
    abstained = res["outcome"] == "abstain"
    text = norm(res.get("claims_text", ""))
    r = {"abstained": abstained, "should_abstain": bool(q.get("should_abstain"))}
    if q.get("should_abstain"):
        r["correct"] = abstained
        return r
    has_exp = (all(norm(e) in text for e in q.get("expected_all", [])) and
               (not q.get("expected_any") or any(norm(e) in text for e in q["expected_any"])))
    r["correct"] = (not abstained) and has_exp
    stale = [norm(s) for s in q.get("stale", [])]
    r["stale_error"] = (not abstained) and bool(stale) and any(s in text for s in stale) and not has_exp
    r["over_refusal"] = abstained
    r["stale_any"] = (not abstained) and any(s in text for s in stale)  # stale value shown at all, even next to the right one
    return r


def evaluate(pipe, qs, modes, verbose=False, pace=0.0):
    rows = []
    last = 0.0
    for mode in modes:
        for q in qs:
            if pace:  # stay under the provider's tokens-per-minute limit
                time.sleep(max(0.0, last + pace - time.time()))
                last = time.time()
            before = dict(TOKENS)
            res = _ask(pipe, q, mode)
            j = judge(q, res)
            row = {"mode": mode, "id": q["id"], "category": q["category"], **j,
                   "coverage": res.get("coverage"), "n_verified": res.get("n_verified", 0), "latency_ms": res["latency_ms"],
                   "outcome": res["outcome"], "language": res.get("language"),
                   "llm_calls": TOKENS["calls"] - before["calls"], "tokens": TOKENS["total"] - before["total"],
                   "truncated": TOKENS["truncated"] - before["truncated"]}
            # retrieval recall on the raw ranked list (before any filtering)
            gold = q.get("gold", [])
            for k in (5, 10):
                top = [pipe.by_id[i] for i in res["retrieved_ids"][:k]]
                row[f"recall@{k}"] = (all(any(gold_hit(c, g) for c in top) for g in gold) if gold else None)
            # citation support: verifier-confirmed claims, and cited passage contains gold evidence
            cl = res.get("claims", [])
            row["cit_verified"] = (sum(1 for c in cl if c.get("verified")), len(cl))
            cited = [pipe.by_id[ci["chunk_id"]] for c in cl for ci in c["citations"] if ci["chunk_id"] in pipe.by_id]
            row["cit_gold"] = (any(gold_hit(c, g) for c in cited for g in gold) if gold and cl else None)
            row["answer"] = res["claims_text"][:160]
            row["reason"] = res.get("abstain_reason")
            row["english_query"] = res.get("english_query")
            rows.append(row)
            print(f"  {mode:15} {q['id']} {res['outcome']:8} correct={row['correct']!s:5} tokens={row['tokens']:5} "
                  f"{res['claims_text'][:90]!r}", file=sys.stderr)
            if verbose and mode == "evidence_aware" and not row["correct"]:
                print(f"  [FAIL {q['id']} {q['category']}] {q['question']}\n     outcome={res['outcome']} reason={res.get('abstain_reason')} "
                      f"cov={res.get('coverage')}\n     answer={res['claims_text'][:200]!r}")
    return rows


def pct(n, d):
    return f"{100 * n / d:5.1f}%" if d else "  n/a "


def summarize(rows, modes):
    print(f"\n{'metric':34}" + "".join(f"{m:>16}" for m in modes))
    def line(name, fn):
        print(f"{name:34}" + "".join(f"{fn([r for r in rows if r['mode'] == m]):>16}" for m in modes))
    line("Answer accuracy", lambda R: pct(sum(r["correct"] for r in R), len(R)))
    line("Recall@5", lambda R: pct(sum(1 for r in R if r["recall@5"]), sum(1 for r in R if r["recall@5"] is not None)))
    line("Recall@10", lambda R: pct(sum(1 for r in R if r["recall@10"]), sum(1 for r in R if r["recall@10"] is not None)))
    line("Stale-policy error rate", lambda R: pct(sum(1 for r in R if r.get("stale_error")), sum(1 for r in R if not r["should_abstain"])))
    line("Stale value shown (any, strict)", lambda R: pct(sum(1 for r in R if r.get("stale_any")), sum(1 for r in R if not r["should_abstain"])))
    line("Citation support (verifier)", lambda R: pct(sum(r["cit_verified"][0] for r in R), sum(r["cit_verified"][1] for r in R)))
    line("Gold-evidence cited", lambda R: pct(sum(1 for r in R if r["cit_gold"]), sum(1 for r in R if r["cit_gold"] is not None)))
    def abst(R, which):
        tp = sum(1 for r in R if r["abstained"] and r["should_abstain"])
        fp = sum(1 for r in R if r["abstained"] and not r["should_abstain"])
        fn = sum(1 for r in R if not r["abstained"] and r["should_abstain"])
        return pct(tp, tp + fp) if which == "p" else pct(tp, tp + fn)
    line("Abstention precision", lambda R: abst(R, "p"))
    line("Abstention recall", lambda R: abst(R, "r"))
    line("Over-refusal (answerable Qs)", lambda R: pct(sum(1 for r in R if r.get("over_refusal")), sum(1 for r in R if not r["should_abstain"])))
    line("Mean latency (ms)", lambda R: f"{sum(r['latency_ms'] for r in R) / max(1, len(R)):.1f}")
    print("\nAccuracy by category (evidence_aware vs others)")
    cats = sorted({r["category"] for r in rows})
    print(f"{'category':14}" + "".join(f"{m:>16}" for m in modes))
    for c in cats:
        print(f"{c:14}" + "".join(
            f"{pct(sum(r['correct'] for r in rows if r['mode'] == m and r['category'] == c), sum(1 for r in rows if r['mode'] == m and r['category'] == c)):>16}"
            for m in modes))


def sweep(rows):
    ea = [r for r in rows if r["mode"] == "evidence_aware"]
    print("\nAbstention-threshold sweep (evidence_aware, coverage-based; reason-based abstentions kept as-is)")
    print(f"{'threshold':>10}{'abst.prec':>11}{'abst.rec':>10}{'over-refusal':>14}{'accuracy':>10}")
    for thr in [0.3, 0.4, 0.5, 0.55, 0.6, 0.7, 0.8]:
        tp = fp = fn = acc = ans = ref = 0
        for r in ea:
            pred = r["abstained"] if r["coverage"] is None else (r["abstained"] and not str(r["reason"]).startswith("low evidence")) or (r["coverage"] is not None and r["coverage"] < thr)
            tp += pred and r["should_abstain"]; fp += pred and not r["should_abstain"]; fn += (not pred) and r["should_abstain"]
            ans += not r["should_abstain"]; ref += pred and not r["should_abstain"]
            acc += (pred if r["should_abstain"] else (not pred and r["correct"]))
        print(f"{thr:>10}{pct(tp, tp + fp):>11}{pct(tp, tp + fn):>10}{pct(ref, ans):>14}{pct(acc, len(ea)):>10}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all", choices=["all", "dev", "test"])
    ap.add_argument("--modes", nargs="+", default=MODES)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--benchmark", default=None, help="question file (default eval/benchmark.jsonl)")
    ap.add_argument("--out", default=None, help="results CSV (default eval/results/per_question.csv)")
    ap.add_argument("--pace", type=float, default=0.0, help="minimum seconds between questions (e.g. 16 for Groq free tier)")
    a = ap.parse_args()
    _install_token_meter()
    t0 = time.time()
    pipe = get_pipeline()
    startup = {"seconds": round(time.time() - t0, 1), "llm_calls": TOKENS["calls"], "tokens": TOKENS["total"],
               "amendments": sorted(x["id"] for x in pipe.amendments)}
    print(f"startup {startup['seconds']}s, {startup['llm_calls']} LLM calls, {startup['tokens']} tokens, "
          f"amendments kept: {startup['amendments']}")
    qs = load_benchmark(a.split, a.benchmark)
    print(f"{len(qs)} questions | split={a.split} | dense backend: {pipe.retriever.dense.backend} | "
          f"generator: {type(pipe.generator).__name__} | rerank: {'cross-encoder' if pipe.retriever.rerank_available() else 'unavailable (no-op)'}")
    rows = evaluate(pipe, qs, a.modes, a.verbose, a.pace)
    summarize(rows, a.modes)
    if a.sweep:
        sweep(rows)
    out_csv = Path(a.out) if a.out else HERE / "results" / "per_question.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    flat = [{k: (json.dumps(v) if isinstance(v, tuple) else v) for k, v in r.items()} for r in rows]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0]))
        w.writeheader()
        w.writerows(flat)
    print(f"\nper-question results -> {out_csv}")
    if a.out:  # run summary next to a custom results file
        summary = {"startup": startup, "questions": len(qs), "modes": a.modes, "per_mode": {}}
        for m in a.modes:
            R = [r for r in rows if r["mode"] == m]
            ans = [r for r in R if not r["should_abstain"]]
            multi = [r for r in R if r["category"] in ("hinglish", "hindi")]
            summary["per_mode"][m] = {
                "accuracy": round(sum(r["correct"] for r in R) / len(R), 4),
                "stale_errors": sum(1 for r in R if r.get("stale_error")),
                "abstention_rate": round(sum(r["abstained"] for r in R) / len(R), 4),
                "abstention_recall": round(sum(r["abstained"] for r in R if r["should_abstain"]) / max(1, len(R) - len(ans)), 4),
                "over_refusal": round(sum(r["abstained"] for r in ans) / max(1, len(ans)), 4),
                "hinglish_hindi_correct": f"{sum(r['correct'] for r in multi)}/{len(multi)}",
                "errors": sum(1 for r in R if r["outcome"] == "error"),
                "avg_tokens": round(sum(r["tokens"] for r in R) / len(R), 1),
                "avg_latency_ms": round(sum(r["latency_ms"] for r in R) / len(R), 1),
                "truncated_replies": sum(r["truncated"] for r in R),
            }
        out_csv.with_suffix(".json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
