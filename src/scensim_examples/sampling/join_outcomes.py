"""Pair each outcome of a search runner with its sample record, for `scensim-sample coverage`.

    python3 join_outcomes.py <stage records .jsonl> <runner outcomes .jsonl> -o <joined .jsonl>

The runner's rows name a record by its id; coverage reads whole records. Every record must have
exactly one outcome, and every outcome a record.
"""
import argparse
import json
import sys


def rows(path):
    return [json.loads(x) for x in open(path) if x.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("records")
    ap.add_argument("outcomes")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    recs = {r["id"]: r for r in rows(a.records)}
    outs = {}
    for o in rows(a.outcomes):
        if o["record"] in outs:
            sys.exit(f"{a.outcomes}: record {o['record']} twice")
        outs[o["record"]] = o["outcome"]
    if set(recs) != set(outs):
        sys.exit(f"{len(set(recs) - set(outs))} records without an outcome, "
                 f"{len(set(outs) - set(recs))} outcomes without a record")
    with open(a.output, "w") as f:
        for i, r in recs.items():
            f.write(json.dumps({"record": r, "outcome": outs[i]}) + "\n")
    print(f"{len(recs)} records joined to {a.output}")


if __name__ == "__main__":
    main()
