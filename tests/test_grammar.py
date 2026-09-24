"""The page grammar: context rows (a sub-page inherits its parent's family, the
neighbours and position are read off the page), rule mining (lift and support,
a pair kept only when it beats its parts, one rule per slot set), the backoff
priors and the `# unusual:` flag, the skeleton's `> prior:` line, the brief's
duration fallback, the doc renderer and doctor's checks."""

import json

import pytest

from landing_page_gen.corpus import db, doctor, grammar, skeleton

from test_brief import load_brief


def _page(con, slug, family, sections):
    """sections: [(type, headline, [(kind, src, duration)])]."""
    cur = con.execute("INSERT INTO pages (slug, url, family, title, fetched_at, html_path) VALUES (?,?,?,?,?,?)",
                      (slug, f"https://picsart.com/{slug}/", family, slug, "2026-09-23", f"corpus/pages/{slug}/index.html"))
    pid = cur.lastrowid
    for i, (typ, head, media) in enumerate(sections):
        sid = f"S{i + 1:02d}"
        sec = con.execute("INSERT INTO sections (page_id, sid, idx, type, headline, md, text_len, media_count) "
                          "VALUES (?,?,?,?,?,?,?,?)", (pid, sid, i, typ, head, head, len(head), len(media))).lastrowid
        con.execute("INSERT INTO texts (section_id, tid, tag, text, selector) VALUES (?,?,?,?,?)",
                    (sec, f"{sid}-t1", "h2", head, "h2"))
        for j, (kind, src, dur) in enumerate(media):
            con.execute("INSERT INTO media (section_id, slot_id, kind, role, src, width, height, aspect, duration, "
                        "style, attrs, selector) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (sec, f"{sid}-m{j + 1}", kind, "creative", src, 480, 480, "1:1", dur, "full-bleed",
                         json.dumps({"subject": "person", "art_style": "photo",
                                     **({"motion_kind": "ui-demo", "pace": "slow", "loop": True} if kind == "video" else {})}),
                         f"#{sid}-m{j + 1}"))


def corpus(tmp_path, n=12):
    """n tool pages: hero image -> a video callout that talks about video ->
    a callout after it (video) -> gallery images -> footer; plus n pages whose
    callouts are stills, and a sub-page with no family of its own."""
    con = db.connect(tmp_path / "c.db")
    for p in range(n):
        _page(con, f"tool{p}", "tool", [
            ("hero", "Edit photos online", [("image", f"https://cdn/{p:02d}000000-h.png", None)]),
            ("feature-callout", "Animate any video", [("video", f"https://cdn/{p:02d}000001-v.mp4", 8.0 + p % 3)]),
            ("feature-callout", "Share it everywhere", [("video", f"https://cdn/{p:02d}000002-v.mp4", 6.0)]),
            ("gallery", "Made with it", [("image", f"https://cdn/{p:02d}00000{g + 3}-g.png", None) for g in range(3)]),
            ("footer", "Picsart", []),
        ])
        _page(con, f"still{p}", "tool", [
            ("hero", "Remove backgrounds", [("image", f"https://cdn/{p:02d}100000-h.png", None)]),
            ("feature-callout", "Crop in one tap", [("image", f"https://cdn/{p:02d}100001-c.png", None)]),
            ("footer", "Picsart", []),
        ])
    _page(con, "tool0--sub", None, [("hero", "Sub page", [("image", "https://cdn/ff000000-h.png", None)])])
    con.commit()
    return con


def test_a_sub_page_takes_its_nearest_ancestors_family(tmp_path):
    con = corpus(tmp_path, n=2)
    fams = grammar.page_families(con)
    assert fams["tool0--sub"] == "tool"
    assert fams["tool1"] == "tool"


def test_context_rows_read_neighbours_position_and_other_videos(tmp_path):
    rows, srows = grammar.contexts(corpus(tmp_path, n=2))
    r = {(x["page"], x["slot"]): x for x in rows}
    first = r[("tool0", "S02-m1")]
    assert (first["prev"], first["next"], first["pos"]) == ("hero", "feature-callout", "upper")
    assert "motion" in first["cues"] and first["page_other_video"] and not first["prev_video"]
    second = r[("tool0", "S03-m1")]
    assert second["prev_video"] and second["page_other_video"]
    alone = r[("still0", "S02-m1")]
    assert not alone["page_other_video"] and alone["kind"] == "image" and alone["length"] is None
    assert r[("tool0", "S02-m1")]["length"] == "6-10s"
    assert [s["type"] for s in srows if s["page"] == "tool0"][-1] == "footer"


def test_mining_measures_lift_and_keeps_a_pair_only_when_it_beats_its_parts():
    base = {"pfam": "tool", "size": "card", "aspect": "1:1", "pos": "upper", "next": "end", "cues": [], "words": [],
            "sib_video": False, "page_other_video": False}
    rows = ([{**base, "page": f"p{i % 5}", "type": "callout", "prev": "video", "kind": "video"} for i in range(20)]
            + [{**base, "page": f"p{i % 5}", "type": "callout", "prev": "hero", "kind": "image"} for i in range(20)]
            + [{**base, "page": f"p{i % 5}", "type": "gallery", "prev": "hero", "kind": "image"} for i in range(60)])
    rules = grammar.mine(rows, decisions=("kind",), min_support=5)["kind"]
    whens = {r["when"]: r for r in rules if r["then"] == "video"}
    top = whens["prev=video"]
    assert (top["n"], top["of"], top["conf"], top["lift"], top["clusters"]) == (20, 20, 1.0, 5.0, 5)  # base 20/100
    assert "prev=video & type=callout" not in whens, "the pair adds nothing over prev=video alone"
    # type=callout alone: 20/40 = 0.5, lift 2.5 — kept, it is a different slot set
    assert whens["type=callout"]["lift"] == 2.5
    same_set = [r for r in rules if (r["then"], r["n"], r["of"]) == ("video", 20, 20)]
    assert len(same_set) == 1, "rules naming one slot set three ways collapse to the simplest"


@pytest.fixture
def built(tmp_path):
    con = corpus(tmp_path)
    g, rows, rules = grammar.build(con, min_support=3)
    return con, g, rows


def test_a_rule_seen_on_one_template_cluster_is_dropped():
    base = {"pfam": "tool", "size": "card", "aspect": "1:1", "pos": "upper", "next": "end", "cues": [], "words": [],
            "sib_video": False, "page_other_video": False, "prev": "hero"}
    # 30 sibling pages of one CMS template all carry a video gallery; 3 other clusters carry still galleries
    rows = ([{**base, "page": f"design--p{i}", "type": "gallery", "kind": "video"} for i in range(30)]
            + [{**base, "page": f"tool{i % 3}", "type": "gallery", "kind": "image"} for i in range(30)]
            + [{**base, "page": f"tool{i % 3}", "type": "hero", "kind": "image"} for i in range(60)])
    whens = {r["when"] for r in grammar.mine(rows, decisions=("kind",), min_support=5)["kind"] if r["then"] == "video"}
    assert not whens, "thirty copies of one template are one piece of evidence"
    assert grammar.cluster("design--flyer") == grammar.cluster("design") == "design"


def test_evaluate_scores_the_priors_on_held_out_page_clusters(built):
    _, g, rows = built
    ev = g["evaluation"]
    assert ev is not None and ev["held_out_slots"] > 0
    assert set(ev) >= {"video_brier", "style_top1", "style_top3", "length_mae_s"}
    assert "How much to trust it" in grammar.render_doc(g)


def test_priors_back_off_and_flag_an_unusual_kind(built, monkeypatch):
    con, g, rows = built
    key, e = grammar.lookup(g["priors"]["kind"], {"type": "gallery", "pfam": "tool", "size": "card"})
    assert key == "gallery|tool|card" and e["video"] == 0
    key, e = grammar.lookup(g["priors"]["kind"], {"type": "gallery", "pfam": "hub", "size": "card"})
    assert key == "gallery", "an unseen page family backs off to the type"
    monkeypatch.setattr(grammar, "UNUSUAL_N", 10)
    odd = {**next(r for r in rows if r["type"] == "gallery"), "kind": "video"}
    assert "a video where 0 % of gallery×tool×card slots are" in grammar.prior(g, odd)["unusual"]
    normal = next(r for r in rows if r["type"] == "gallery")
    assert grammar.prior(g, normal)["unusual"] is None
    line = grammar.prior_line(g, next(r for r in rows if r["page"] == "tool0" and r["sid"] == "S03"))
    assert line.startswith("video ") and "length 7" in line and "basis feature-callout×tool" in line


def test_sequences_give_the_families_typical_order(built):
    _, g, _ = built
    canon = [t for t, _, _ in g["sequences"]["tool"]["canonical"]]
    assert canon[0] == "hero" and canon[-1] == "footer" and "feature-callout" in canon


def test_skeleton_writes_a_prior_line_per_generated_slot(built):
    con, g, _ = built
    page, sections = skeleton.load_page(con, "tool0")
    text = skeleton.render_skeleton(page, sections, g, "tool")
    assert "page_family: tool" in text
    assert text.count("> prior: video") == 6  # hero, two callouts, three gallery tiles
    assert "> prior:" not in skeleton.render_skeleton(page, sections)


def test_brief_takes_the_grammar_median_when_no_length_is_known():
    brief = load_brief()
    prior = "video 40 % · motion ui-demo, loop 50 % · length 7.6 s (IQR 6-9) · basis feature-callout×tool n=24"
    assert brief.target_duration({}, None, 30, prior) == (
        8, "no original length; the page grammar's median for feature-callout×tool")
    assert brief.target_duration({"duration_s": 12.2}, None, 30, prior)[0] == 12, "the original's length stands"
    assert brief.target_duration({}, "10", 30, prior)[0] == 10, "the manager's line stands"
    assert brief.target_duration({}, None, 30, "video 0 % · basis hero n=40")[0] == 5


def test_doc_render_is_stable_and_doctor_checks_it(built, tmp_path):
    con, g, _ = built
    path = grammar.save(g, tmp_path / "grammar.yaml")
    doc = tmp_path / "page-grammar.md"
    doc.write_text(grammar.render_doc(grammar.load(path)))
    assert grammar.render_doc(grammar.load(path)) == doc.read_text()
    assert grammar.render_doc(g) == doc.read_text(), "yaml round-trip changes nothing"
    assert doctor._grammar(con, path, doc) == []
    doc.write_text(doc.read_text() + "hand edit\n")
    assert [f.code for f in doctor._grammar(con, path, doc)] == ["grammar-doc"]
    con.execute("UPDATE sections SET headline = 'changed' WHERE sid = 'S02'")
    assert "grammar-stale" in [f.code for f in doctor._grammar(con, path, doc)]
    assert doctor._grammar(con, None, None) == [], "tests and callers without a grammar skip the check"
