"""Manager's paperwork check of one section before any reviewer is spawned.

    uv run python .claude/skills/build-landing-page/precheck.py runs/<run> S03

Reads workflow.yaml, result.md and the run ledger and prints one line per
problem; exit 0 when the record is clean (pixels still need the reviewer),
exit 1 otherwise. Catches what a review round used to catch for free: a paid
step without a preflight, `count` above 1, a gate without an observation,
credits.spent off the ledger, a final file that is not on disk, a compose
spec whose `variant:` contradicts the brief's `> device:` line, a Flow board
that does not wire (`lp-flow check`), a final clip off the brief's target
duration, a clip URL that never passed through `picsart_job_status` (so the
ledger cannot own it), extra video renders beyond the board's nodes (the
orphaned finals that cost live-5 ~190 credits), and a hybrid `rendered_by:
model` plan item that no node claims (or a node that claims one the plan does
not mark)."""
import json
import re
import sys
from pathlib import Path

import yaml

from landing_page_gen.compose import cli as compose_cli
from landing_page_gen.compose.families import FAMILIES
from landing_page_gen.flow import board

PAID = {"picsart_generate", "picsart_enhance", "picsart_remove_bg", "picsart_change_bg", "picsart_vectorize"}
DURATION_TOLERANCE = 1  # seconds a final clip may sit off the brief's target
TARGET_RE = re.compile(r"^\s*- (S\d+-m\d+): \*\*(\d+) s\*\*", re.M)


def prompt_of(row):
    p = row.get("params") or {}
    return (p.get("prompt") or (p.get("params") or {}).get("prompt") or "").strip()


def video_targets(folder):
    """{slot: target seconds} from the brief's `## Video` section."""
    brief = folder / "brief.md"
    return {s: int(t) for s, t in TARGET_RE.findall(brief.read_text())} if brief.exists() else {}


def video_problems(doc, steps, rows, targets):
    """The video half of a record: the final's `duration` against the brief's
    target, every done clip's URL in a job_status row, and no more paid video
    rows for a prompt than the board has nodes for it."""
    slot = doc.get("slot", "?")
    out = []
    videos = [s for s in steps if s["node"] == "video"]
    if not videos:
        return out
    job_urls = {u.split("?")[0] for r in rows if r.get("tool") == "picsart_job_status" for u in r.get("urls") or []}
    target = targets.get(slot)
    for s in videos:
        sid_ = f"{slot} step {s.get('id')}"
        params = s.get("params") or {}
        final = board.VIDEO_DRAFT_HINT not in (s.get("model") or "")
        if final and target and s.get("status") == "done" and abs((params.get("duration") or 0) - target) > DURATION_TOLERANCE:
            out.append(f"{sid_}: duration {params.get('duration')} but the brief's target is {target} s")
        if s.get("status") == "done" and rows:
            urls = [u for u in (s.get("outputs") or []) if str(u).startswith("http")]
            if not urls:
                out.append(f"{sid_}: done video node with no clip URL in outputs (write it the instant job_status returns it)")
            for u in urls:
                if str(u).split("?")[0] not in job_urls:
                    out.append(f"{sid_}: clip {u} is in no picsart_job_status ledger row; poll through job_status so the ledger owns it")
    by_key = {}
    for s in videos:
        key = (s.get("model"), ((s.get("params") or {}).get("prompt") or "").strip())
        by_key[key] = by_key.get(key, 0) + 1
    for (model, prompt), n_nodes in by_key.items():
        n_rows = sum(1 for r in rows if r.get("tool") in PAID and r.get("model") == model and prompt_of(r) == prompt)
        if n_rows > n_nodes:
            out.append(f"{slot}: {n_rows - n_nodes} extra {model} ledger row(s) for the prompt {prompt[:40]!r}: orphaned "
                       f"render(s) beyond the board's {n_nodes} node(s); annotate them so the slot total is auditable")
    return out


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
    # credits are owned by the URL a paid call produced, so a reworked node that
    # re-ran the same prompt is not double-counted against the kept output. Rows
    # with no URL (a failed/uncharged call, an old record) fall back to a
    # per-prompt bucket, which is the pre-URL behaviour.
    spent_by_url, spent_by_prompt = {}, {}
    for r in rows:
        if r.get("tool") not in PAID:
            continue
        urls = r.get("urls") or []
        if urls:
            for u in urls:
                spent_by_url[u] = r.get("quoted_credits") or 0
        else:
            spent_by_prompt[prompt_of(r)] = spent_by_prompt.get(prompt_of(r), 0) + (r.get("quoted_credits") or 0)
    targets = video_targets(folder)
    for d in docs:
        slot = d.get("slot", "?")
        problems += board.check(d)
        problems += compose_wiring_problems(d, folder)
        problems += video_problems(d, board.nodes(d), rows, targets)
        prompts, urls = set(), set()  # reconcile by the URLs a board's steps produced, else by prompt
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
                prompts.add(prompt)
                urls.update(st.get("outputs") or [])
            if st.get("status") == "done" and not (st.get("note") or "").strip():
                problems.append(f"{sid_}: done without a gate observation in note")
            if not (st.get("gate") or "").strip():
                problems.append(f"{sid_}: gate empty")
        credits = d.get("credits") or {}
        # URLs the board kept (exact), plus a fallback for prompts whose rows had no URL
        prompts_without_url = {pr for pr in prompts if pr not in {prompt_of(r) for r in rows if (r.get("urls") and r.get("tool") in PAID)}}
        ledger_sum = sum(spent_by_url.get(u, 0) for u in urls) + sum(spent_by_prompt.get(pr, 0) for pr in prompts_without_url)
        if credits.get("spent") is not None and credits["spent"] != ledger_sum:
            problems.append(f"{slot}: credits.spent {credits['spent']} != ledger {ledger_sum} for its outputs")
        final = d.get("final") or {}
        if final.get("local") and not (folder / final["local"]).exists():
            problems.append(f"{slot}: final.local {final['local']} not on disk")
    if res_path.exists():
        text = res_path.read_text()
        for key in ("chosen:", "scores:"):
            if key not in text:
                problems.append(f"result.md lacks {key}")
    if not (folder / "flow.md").exists():
        problems.append("flow.md missing (uv run lp-flow sheet workflow.yaml)")
    problems += device_problems(folder)
    problems += composition_problems(folder)
    problems += label_problems(folder)
    problems += hybrid_problems(folder)
    return problems


def device_problems(folder):
    """The brief's `> device: <id>: ...` against each compose spec's `variant:`:
    when the family draws that device as a variant, the spec must name it,
    and a spec must not name a variant the brief did not ask for — except the
    one its size selects when the default's aspect does not fit
    (`compose.cli.preset_for_size`, e.g. before-after `stacked-square` at 1:1)."""
    brief = folder / "brief.md"
    m = re.search(r"^> device: ([a-z-]+)", brief.read_text(), re.M) if brief.exists() else None
    device = m.group(1) if m else None
    out = []
    for spec_path in sorted(folder.glob("compose-*.yaml")):
        spec = yaml.safe_load(spec_path.read_text()) or {}
        variants = (FAMILIES.get(spec.get("family")) or {}).get("variants") or {}
        variant = spec.get("preset") or spec.get("variant")
        slot_size = _slot_size(folder, spec_path.stem[len("compose-"):])  # never the spec's own size: the worker writes that
        fitted = None if device in variants else compose_cli.preset_for_size(spec.get("family"), slot_size)
        if (device in variants and variant != device) or (variant and variant not in (device, fitted)):
            out.append(f"{spec_path.name}: compose variant {variant or 'none'} but brief device {device or 'none'}")
    return out


def _slot_size(folder, slot):
    """A slot's real size, from what the manager wrote: its composition plan,
    else the run's slots.json; None when neither says."""
    plan_path = folder / f"composition-{slot}.yaml"
    if plan_path.exists():
        size = (yaml.safe_load(plan_path.read_text()) or {}).get("size")
        if size:
            return size
    slots_path = folder.parent.parent / "slots.json"
    if slots_path.exists():
        size = ((json.loads(slots_path.read_text()).get("slots") or {}).get(slot) or {}).get("size")
        if size:
            return tuple(size)
    return None


def compose_wiring_problems(doc, folder):
    """A compose node, once rendered, must name a spec that exists, agree with
    the board's family, and be fed (`in:`) by every node whose step file is one
    of its panel images."""
    out = []
    slot = doc.get("slot", "?")
    steps = doc.get("steps") or []
    for st in steps:
        if (st.get("node") or board.infer_node(st)) != "compose":
            continue
        spec_name = (st.get("params") or {}).get("spec")
        if not spec_name:
            out.append(f"{slot}: compose node {st.get('id')} has no params.spec")
            continue
        spec_path = folder / spec_name
        if not spec_path.exists():
            if st.get("status") == "done":
                out.append(f"{slot}: compose spec {spec_name} not on disk though the node ran")
            continue  # planned/skipped: the worker writes it during the run
        spec = yaml.safe_load(spec_path.read_text()) or {}
        if spec.get("family") and doc.get("family") and spec["family"] != doc["family"]:
            out.append(f"{slot}: compose spec family {spec['family']!r} != board family {doc['family']!r}")
        ins = set(st.get("in") or board.infer_in(st, steps))
        for p in (spec.get("panels") or {}).values():
            m = re.search(r"-(\d+)-\d+\.\w+$", (p or {}).get("image") or "")  # steps/<slot>-<node>-<n>.<ext>
            if m and int(m.group(1)) not in ins:
                out.append(f"{slot}: compose node {st.get('id')} is not fed by node {m.group(1)} (panel {p['image']})")
    return out


def composition_problems(folder):
    """A compose spec built from a plan must still match it: the worker adds
    image paths, it does not re-plan. A spec that names a plan (`plan:`) must
    find it and agree on family and preset."""
    out = []
    for spec_path in sorted(folder.glob("compose-*.yaml")):
        spec = yaml.safe_load(spec_path.read_text()) or {}
        plan_name = spec.get("plan")
        if not plan_name:  # a hand-written spec with no plan is allowed
            continue
        plan_path = folder / plan_name
        if not plan_path.exists():
            out.append(f"{spec_path.name}: names plan {plan_name}, which is missing")
            continue
        cp = yaml.safe_load(plan_path.read_text()) or {}
        if spec.get("family") != cp.get("family"):
            out.append(f"{spec_path.name}: family {spec.get('family')!r} != plan {cp.get('family')!r}")
        if (spec.get("preset") or spec.get("variant")) != cp.get("preset"):
            out.append(f"{spec_path.name}: preset {spec.get('preset') or spec.get('variant')!r} != plan {cp.get('preset')!r}")
    return out


TEXT_FIELDS = ("text", "label", "title", "active_text", "sliders", "colours")


def label_problems(folder):
    """The strings a compose spec draws are its plan's, exactly (the plan carries
    the manager's `> chrome:` strings): the worker adds image paths and never
    relabels, drops or adds a string. An item the spec leaves out would draw the
    template's string, so it counts as a relabel too."""
    out = []
    for spec_path in sorted(folder.glob("compose-*.yaml")):
        spec = yaml.safe_load(spec_path.read_text()) or {}
        plan_path = folder / (spec.get("plan") or "")
        if not spec.get("plan") or not plan_path.exists():
            continue  # no plan to hold it to; composition_problems reports a missing one
        cp = yaml.safe_load(plan_path.read_text()) or {}
        planned = {it.get("id"): it for it in cp.get("items") or [] if it.get("rendered_by") != "model"}
        drawn = compose_cli._chrome_entries(spec)
        for cid in [*planned, *(c for c in drawn if c not in planned)]:
            want, got = planned.get(cid) or {}, drawn.get(cid) or {}
            for key in TEXT_FIELDS:
                if (key in want or key in got) and want.get(key) != got.get(key):
                    out.append(f"{spec_path.name}: {cid} {key} is {got.get(key)!r}, the plan's is {want.get(key)!r}")
    return out


def hybrid_problems(folder):
    """Pair a plan's `rendered_by: model` items with the workflow nodes that
    render them (the hybrid gate): each hybrid item needs exactly one node
    carrying its `chrome_item:`, each such node must name a hybrid item that the
    plan marks model-rendered, and the node's prompt must mention that item (by
    id or kind). board.check already enforces the node shape; this is the
    cross-file half, which needs the composition plan."""
    out = []
    wf_path = folder / "workflow.yaml"
    if not wf_path.exists():
        return out
    for d in (x for x in yaml.safe_load_all(wf_path.read_text()) if x):
        slot = d.get("slot", "?")
        plan_path = folder / f"composition-{slot}.yaml"
        cp = (yaml.safe_load(plan_path.read_text()) or {}) if plan_path.exists() else {}
        model_items = {it["id"]: it for it in (cp.get("items") or []) if it.get("rendered_by") == "model" and it.get("id")}
        claimed = {}
        for st in d.get("steps") or []:
            item = st.get("chrome_item")
            if not item:
                continue
            claimed[item] = claimed.get(item, 0) + 1
            if item not in model_items:
                out.append(f"{slot} step {st.get('id')}: chrome_item {item!r} is not a rendered_by: model item in composition-{slot}.yaml")
                continue
            prompt = ((st.get("params") or {}).get("prompt") or "").lower()
            kind = (model_items[item].get("kind") or "").lower()
            if item.lower() not in prompt and (not kind or kind not in prompt):
                out.append(f"{slot} step {st.get('id')}: prompt does not mention the hybrid item {item!r} ({kind or 'no kind'}) it renders")
        for iid in model_items:
            n = claimed.get(iid, 0)
            if n == 0:
                out.append(f"{slot}: hybrid item {iid!r} (rendered_by: model) has no node with chrome_item: {iid}")
            elif n > 1:
                out.append(f"{slot}: hybrid item {iid!r} is claimed by {n} nodes; exactly one node renders it")
    return out


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
