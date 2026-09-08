"""Manager's paperwork check of one section before any reviewer is spawned.

    uv run python .claude/skills/build-landing-page/precheck.py runs/<run> S03

Reads workflow.yaml, result.md and the run ledger and prints one line per
problem; exit 0 when the record is clean (pixels still need the reviewer),
exit 1 otherwise. Catches what a review round used to catch for free: a paid
step without a preflight, `count` above 1, a gate without an observation,
credits.spent off the ledger, a final file that is not on disk."""
import json
import sys
from pathlib import Path

import yaml

PAID = {"picsart_generate", "picsart_enhance", "picsart_remove_bg", "picsart_change_bg", "picsart_vectorize"}


def prompt_of(row):
    p = row.get("params") or {}
    return (p.get("prompt") or (p.get("params") or {}).get("prompt") or "").strip()


def check(run, sid):
    folder = Path(run) / "sections" / sid
    problems = []
    wf_path, res_path = folder / "workflow.yaml", folder / "result.md"
    if not wf_path.exists():
        return [f"{sid}: workflow.yaml missing"]
    if not res_path.exists():
        problems.append("result.md missing")
    docs = [d for d in yaml.safe_load_all(wf_path.read_text()) if d]
    ledger_path = Path(run) / "ledger.jsonl"
    rows = [json.loads(l) for l in ledger_path.read_text().splitlines() if l.strip()] if ledger_path.exists() else []
    quotes = {(r["model"], prompt_of(r)) for r in rows if r.get("tool") == "picsart_preflight"}
    spent_by_prompt = {}
    for r in rows:
        if r.get("tool") in PAID:
            spent_by_prompt[prompt_of(r)] = spent_by_prompt.get(prompt_of(r), 0) + (r.get("quoted_credits") or 0)
    for d in docs:
        slot = d.get("slot", "?")
        ledger_sum = 0
        for st in d.get("steps") or []:
            sid_ = f"{slot} step {st.get('id')}"
            params = st.get("params") or {}
            if st.get("tool") in PAID:
                prompt = (params.get("prompt") or "").strip()
                if (st.get("model"), prompt) not in quotes and st.get("status") not in ("skipped", None):
                    problems.append(f"{sid_}: no preflight row for this model and prompt")
                if int(params.get("count") or 1) > 1:
                    problems.append(f"{sid_}: count {params.get('count')} (use 1)")
                if st.get("quoted_credits") is None:
                    problems.append(f"{sid_}: quoted_credits missing")
                ledger_sum += spent_by_prompt.get(prompt, 0)
            if st.get("status") == "done" and not (st.get("note") or "").strip():
                problems.append(f"{sid_}: done without a gate observation in note")
            if not (st.get("gate") or "").strip():
                problems.append(f"{sid_}: gate empty")
        credits = d.get("credits") or {}
        if credits.get("spent") is not None and credits["spent"] != ledger_sum:
            problems.append(f"{slot}: credits.spent {credits['spent']} != ledger {ledger_sum} for its prompts")
        final = d.get("final") or {}
        if final.get("local") and not (folder / final["local"]).exists():
            problems.append(f"{slot}: final.local {final['local']} not on disk")
    if res_path.exists():
        text = res_path.read_text()
        for key in ("chosen:", "scores:"):
            if key not in text:
                problems.append(f"result.md lacks {key}")
    return problems


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    problems = check(argv[0], argv[1])
    for p in problems:
        print(p)
    print(f"{argv[1]}: {'clean record' if not problems else str(len(problems)) + ' problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
