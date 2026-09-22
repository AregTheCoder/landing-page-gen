"""The manager's precheck reads a section's record against the run ledger and
names every paperwork problem a review round used to catch."""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".claude/skills/build-landing-page/precheck.py"
spec = importlib.util.spec_from_file_location("precheck", SCRIPT)
precheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(precheck)

PROMPT = "a red cup on a yellow seamless, no other text, no logos or watermarks"


def make_run(tmp_path, count=1, spent=5, with_preflight=True, final_exists=True, note="looks right"):
    run = tmp_path / "run"
    sec = run / "sections" / "S03"
    (sec / "steps").mkdir(parents=True)
    if final_exists:
        (sec / "steps" / "S03-m1-1-1.png").write_bytes(b"x")
    (sec / "workflow.yaml").write_text(
        "slot: S03-m1\nsteps:\n  - id: 1\n    tool: picsart_generate\n    model: gemini-3-pro-image\n"
        f"    params: {{prompt: '{PROMPT}', aspectRatio: '4:3', count: {count}}}\n    quoted_credits: 5\n"
        f"    gate: 'one cup, centred'\n    status: done\n    note: '{note}'\n"
        f"final: {{url: x, local: steps/S03-m1-1-1.png}}\ncredits: {{quoted: 5, spent: {spent}}}\n")
    (sec / "result.md").write_text("---\nchosen: x\nscores: {clean: 5}\n---\n")
    (sec / "flow.md").write_text("# Flow board\n")
    rows = []
    if with_preflight:
        rows.append({"tool": "picsart_preflight", "model": "gemini-3-pro-image",
                     "params": {"model": "gemini-3-pro-image", "params": {"prompt": PROMPT}}, "quoted_credits": 5})
    rows.append({"tool": "picsart_generate", "model": "gemini-3-pro-image",
                 "params": {"model": "gemini-3-pro-image", "prompt": PROMPT}, "quoted_credits": 5})
    (run / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return run


def test_clean_record_passes(tmp_path):
    assert precheck.check(make_run(tmp_path), "S03") == []


def test_every_paperwork_problem_is_named(tmp_path):
    problems = precheck.check(make_run(tmp_path, count=2, spent=10, with_preflight=False, final_exists=False, note=""), "S03")
    text = "\n".join(problems)
    assert "no preflight row" in text and "count 2" in text and "credits.spent 10 != ledger 5" in text
    assert "not on disk" in text and "without a gate observation" in text


def test_a_failed_step_rerun_with_the_same_prompt_counts_its_ledger_rows_once(tmp_path):
    run = make_run(tmp_path)
    wf = run / "sections" / "S03" / "workflow.yaml"
    wf.write_text(wf.read_text().replace("steps:\n", "steps:\n  - id: 0\n    tool: picsart_generate\n    model: gemini-3-pro-image\n"
                                         f"    params: {{prompt: '{PROMPT}', aspectRatio: '4:3', count: 1}}\n    quoted_credits: 5\n"
                                         "    gate: 'one cup, centred'\n    status: failed\n    note: 'failure_space_limit_reached, not charged'\n"))
    assert precheck.check(run, "S03") == [], "the ledger holds one paid row for this prompt and the record says 5"


def test_compose_variant_must_match_the_brief_device(tmp_path):
    run = make_run(tmp_path)
    sec = run / "sections" / "S03"
    (sec / "brief.md").write_text("# Brief\n\n> device: reference-thumbs: references in, style-locked output out\n")
    (sec / "compose-S03-m1.yaml").write_text("family: dark-composite\nsize: 720x720\npanels: {photo: {image: steps/S03-m1-1-1.png}}\n")
    assert precheck.check(run, "S03") == ["compose-S03-m1.yaml: compose variant none but brief device reference-thumbs"]
    (sec / "compose-S03-m1.yaml").write_text("family: dark-composite\nvariant: reference-thumbs\nsize: 720x720\n")
    assert precheck.check(run, "S03") == []
    (sec / "brief.md").write_text("# Brief\n\n> device: icon-set: one style, many items\n")
    assert precheck.check(run, "S03") == ["compose-S03-m1.yaml: compose variant reference-thumbs but brief device icon-set"]
    (sec / "compose-S03-m1.yaml").write_text("family: dark-composite\nsize: 720x720\n")
    assert precheck.check(run, "S03") == [], "icon-set is carried by the annotation, so the plain template is right"


CLIP = "https://gcdn.picsart.com/editing-temp/final.mp4"
DRAFT = "https://gcdn.picsart.com/editing-temp/draft.mp4"
MOTION = "the subject blinks, camera holds, no other text, no logos or watermarks"


def video_run(tmp_path, duration=10, job_rows=True, extra_final=False):
    run = make_run(tmp_path)
    sec = run / "sections" / "S03"
    (sec / "steps" / "S03-m1-3-1.mp4").write_bytes(b"x")
    node = ("  - id: {i}\n    node: video\n    in: [1]\n    tool: picsart_generate\n    model: {model}\n"
            "    params: {{prompt: '" + MOTION + "', aspectRatio: '1:1', resolution: 720p, duration: {dur}, "
            "generateAudio: false, async: true, extra: {{startFrame: '<step 1 passed>'}}}}\n"
            "    quoted_credits: {q}\n    gate: 'first frame equals the still'\n    status: done\n    note: 'steady'\n"
            "    outputs: ['{url}']\n")
    wf = sec / "workflow.yaml"
    text = wf.read_text().replace("slot: S03-m1\n", "slot: S03-m1\nkind: video\n")
    text = text.replace("final:", node.format(i=2, model="seedance-2.0-mini", dur=5, q=10, url=DRAFT)
                        + node.format(i=3, model="seedance-2.5", dur=duration, q=35, url=CLIP) + "final:")
    text = text.replace("final: {url: x, local: steps/S03-m1-1-1.png}", "final: {url: " + CLIP + ", local: steps/S03-m1-3-1.mp4}")
    text = text.replace("credits: {quoted: 5, spent: 5}", "credits: {quoted: 50, spent: 50}")
    wf.write_text(text)
    (sec / "brief.md").write_text("# Brief\n\n## Video\n\n- Target duration:\n  - S03-m1: **10 s** (original 9.8 s)\n\n## Text in image\n")
    rows = [json.loads(l) for l in (run / "ledger.jsonl").read_text().splitlines()]
    for model, q, url in (("seedance-2.0-mini", 10, DRAFT), ("seedance-2.5", 35, CLIP)):
        rows.append({"tool": "picsart_preflight", "model": model, "params": {"model": model, "params": {"prompt": MOTION}}, "quoted_credits": q})
        rows.append({"tool": "picsart_generate", "model": model, "params": {"model": model, "params": {"prompt": MOTION}}, "quoted_credits": q, "urls": []})
        if job_rows:
            rows.append({"tool": "picsart_job_status", "model": None, "params": {"jobId": "j"}, "urls": [url], "quoted_credits": None})
    if extra_final:
        rows.append({"tool": "picsart_generate", "model": "seedance-2.5", "params": {"model": "seedance-2.5", "params": {"prompt": MOTION}}, "quoted_credits": 35, "urls": []})
    (run / "ledger.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return run


def test_video_record_is_checked_for_target_duration_job_rows_and_orphans(tmp_path):
    assert precheck.check(video_run(tmp_path), "S03") == []
    short = "\n".join(precheck.check(video_run(tmp_path / "short", duration=5), "S03"))
    assert "step 3: duration 5 but the brief's target is 10 s" in short and "step 2" not in short, "the draft stays at 5 s"
    unowned = "\n".join(precheck.check(video_run(tmp_path / "unowned", job_rows=False), "S03"))
    assert f"clip {CLIP} is in no picsart_job_status ledger row" in unowned
    orphan = "\n".join(precheck.check(video_run(tmp_path / "orphan", extra_final=True), "S03"))
    assert "1 extra seedance-2.5 ledger row(s)" in orphan and "credits.spent 50 != ledger 85" in orphan


def test_cli_exit_codes(tmp_path, capsys):
    run = make_run(tmp_path)
    assert precheck.main([str(run), "S03"]) == 0 and "clean record" in capsys.readouterr().out
    assert precheck.main([str(make_run(tmp_path / "b", count=2)), "S03"]) == 1
    assert precheck.check(tmp_path / "nowhere", "S03") == ["S03: workflow.yaml missing"]


def test_composition_spec_must_match_its_plan(tmp_path):
    sec = tmp_path / "sections" / "S03"
    sec.mkdir(parents=True)
    (sec / "composition-S03-m1.yaml").write_text("family: dark-composite\npreset: model-picker\nsize: 720x720\n")
    # a spec built from the plan (spec-from-plan records `plan:`) agrees -> clean
    (sec / "compose-S03-m1.yaml").write_text(
        "family: dark-composite\npreset: model-picker\nsize: 720x720\nplan: composition-S03-m1.yaml\n")
    assert precheck.composition_problems(sec) == []
    # a spec that re-planned (wrong preset) is caught
    (sec / "compose-S03-m1.yaml").write_text(
        "family: dark-composite\npreset: two-up\nsize: 720x720\nplan: composition-S03-m1.yaml\n")
    assert any("preset" in p for p in precheck.composition_problems(sec))
    # a missing plan is caught
    (sec / "compose-S03-m1.yaml").write_text("family: dark-composite\nplan: composition-gone.yaml\n")
    assert any("missing" in p for p in precheck.composition_problems(sec))
    # a hand-written spec with no plan is allowed
    (sec / "compose-S03-m1.yaml").write_text("family: dark-composite\nsize: 720x720\n")
    assert precheck.composition_problems(sec) == []
