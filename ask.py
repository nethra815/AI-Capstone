"""CLI demo: python ask.py "What is the condonation fee?"

Use --interactive to answer multiple questions without rebuilding the pipeline.
"""
import argparse
import json

from spitrag.pipeline import MODES, get_pipeline

ap = argparse.ArgumentParser()
ap.add_argument("question", nargs="?")
ap.add_argument("--as-of", default=None, help="policy date, YYYY-MM-DD (default: today)")
ap.add_argument("--batch", default=None, help="admission year, e.g. 2024, 2025, 2026")
ap.add_argument("--mode", default="evidence_aware", choices=MODES)
ap.add_argument("--json", action="store_true")
ap.add_argument("--interactive", action="store_true", help="ask multiple questions using one pipeline")
a = ap.parse_args()

def print_result(res):
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
        return
    print(f"\n[{res['outcome'].upper()}]  mode={res['mode']}  as_of={res['as_of']}  batch={res['batch']}  lang={res['language']}")
    print(res["answer"])
    for i, c in enumerate(res.get("claims", []), 1):
        for ci in c["citations"][:1]:
            print(f"\n[{i}] {ci['title']} v{ci['version']} | {ci['section']} | clauses {ci['clauses']} | "
                  f"published {ci['published_on']}, effective {ci['effective_from']} | verified={c['verified']}")
    for cf in res["conflicts"]:
        print(f"\nCONFLICT: {cf['older_source']} says \"{cf['older_says'][:120]}\"\n"
              f"          {cf['newer_source']}: {cf['newer_says']}\n"
              f"          -> applies: {cf['applies']}")
    if res["abstain_reason"]:
        print(f"\n(abstain reason: {res['abstain_reason']})")


if not a.interactive and not a.question:
    ap.error("question is required unless --interactive is used")

pipe = get_pipeline()
if a.interactive:
    print("Pipeline ready. Ask a question, or type 'exit' to quit.")
    while True:
        try:
            question = input("\nquestion> ").strip()
        except EOFError:
            break
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            print_result(pipe.ask(question, as_of=a.as_of, batch=a.batch, mode=a.mode))
else:
    print_result(pipe.ask(a.question, as_of=a.as_of, batch=a.batch, mode=a.mode))
