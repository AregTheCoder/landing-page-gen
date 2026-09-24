"""Which kind of generation Picsart uses for a slot, measured from the corpus.

Three modes, read off each labelled asset's attributes:

- `layered`: a picture inside a template: chrome (tiles, pills, cards, a
  prompt box, a compare handle), several panels, a before/after or a UI mock.
  Our `lp-compose` families.
- `design`: a finished template design generated as one picture with its type
  set in it (a flyer, a card, a post), the gallery of a maker page.
- `standalone`: one generated picture, no chrome and no set type: a sample
  output. Picsart shows these where it showcases many options side by side
  (a horizontally scrolling gallery of characters, styles, subjects) and on
  tutorial thumbnails.

The share of each mode is kept per context (section type x how many images the
section holds x page family, backing off to type x count, then type), and
`expect()` names the modes a slot may take: the leading modes until they hold
`DECIDED` of the context's `MIN_N`+ assets (a single-image callout: layered; a
maker page's gallery: design or layered, never a bare picture). `brief.py` refuses a family of another
mode unless the skeleton carries `> mode: <mode> because <reason>`, and
`manager_check.py` holds the run to it before `lp-inject`."""

import collections
import json
import re
import sqlite3
from functools import lru_cache

MODES = ("standalone", "design", "layered")
DECIDED = 0.7  # the allowed modes are the leading ones until they hold this share
MIN_N = 20
NOT_GENERATED = ("ui-screenshot", "icon", "decorative")
DESIGN_ART = ("typography", "flat-vector", "collage", "mixed")
DESIGN_TEXT = ("headline", "body")
# the families that make each mode (style-families.md: a Template of `none` is
# one model picture; every lp-compose template is layered)
STANDALONE_FAMILIES = ("full-bleed", "cinematic-still", "outcome-tile")
DESIGN_FAMILIES = ("graphic-collage",)  # template-mockup shows a design inside editor chrome: layered
DESIGNED_PAGE = re.compile(r"(maker|design--|templates?|creator|poster|flyer|cards?\b|invitation|logo)")


def mode_of(attrs):
    """The mode of one asset from its attributes (a dict), or None when unlabelled."""
    if not attrs:
        return None
    chrome = [c for c in attrs.get("chrome") or [] if c != "none"]
    if (chrome or (attrs.get("panel_count") or 1) > 1 or attrs.get("before_after")
            or attrs.get("layout") not in (None, "single") or attrs.get("ui_mockup") not in (None, "none")):
        return "layered"
    if attrs.get("text_in_image") in DESIGN_TEXT and attrs.get("art_style") in DESIGN_ART:
        return "design"
    return "standalone"


def family_modes(family, text="none"):
    """The modes a style family can make: a standalone family with set type
    (`> text:` names a headline) is a design as well."""
    if family in STANDALONE_FAMILIES:
        return ("standalone", "design") if text not in (None, "", "none") else ("standalone",)
    if family in DESIGN_FAMILIES:
        return ("design",)
    return ("layered",)


def band(n_media):
    """How many images the section holds: one, a few, or a scrolling set."""
    return "single" if n_media <= 1 else "few" if n_media <= 3 else "many"


def page_kind(slug, family):
    """The page family, with design/maker pages told apart (their galleries are designs)."""
    return "designed" if DESIGNED_PAGE.search(slug or "") else (family or "other")


LEVELS = (("type", "band", "page"), ("type", "band"), ("type",))


def table(con):
    """{level key: Counter(mode)} over every labelled, generated-role image."""
    out = collections.defaultdict(collections.Counter)
    rows = con.execute("""select s.type, s.media_count, p.slug, p.family, m.role, m.attrs from media m
        join sections s on s.id = m.section_id join pages p on p.id = s.page_id
        where m.kind = 'image' and m.attrs is not null""")
    for typ, n, slug, fam, role, attrs in rows:
        if role in NOT_GENERATED:
            continue
        mode = mode_of(json.loads(attrs))
        if not mode:
            continue
        ctx = {"type": typ, "band": band(n), "page": page_kind(slug, fam)}
        for level in LEVELS:
            out["|".join(ctx[k] for k in level)][mode] += 1
    return dict(out)


@lru_cache(maxsize=1)
def load(db="corpus/corpus.db"):
    with sqlite3.connect(db) as con:
        return table(con)


def expect(tab, section_type, n_media, slug="", page_family=None):
    """What the corpus says for this context: {allowed, shares, n, basis}.
    `allowed` is every mode when there is no evidence."""
    ctx = {"type": section_type, "band": band(n_media), "page": page_kind(slug, page_family)}
    for level in LEVELS:
        key = "|".join(ctx[k] for k in level)
        c = tab.get(key)
        if not c or sum(c.values()) < MIN_N:
            continue
        n = sum(c.values())
        allowed, held = [], 0
        for mode, k in c.most_common():
            if held >= DECIDED * n:
                break
            allowed.append(mode)
            held += k
        return {"allowed": allowed, "shares": {m: round(c[m] / n, 2) for m in MODES}, "n": n,
                "basis": key.replace("|", " x ")}
    return {"allowed": list(MODES), "shares": {}, "n": 0, "basis": None}


MEANING = {
    "standalone": "one generated picture, no chrome and no set type: a sample output, each tile of a set a different "
                  "option (subject, character, style) so the row shows the range",
    "design": "a finished template design generated whole as one picture with its type set in it (a flyer, a card, a "
              "post, an ad): `full-bleed` or `graphic-collage` with the strings on `text:`, no chrome; "
              "`template-mockup` is the layered form (the design inside editor chrome)",
    "layered": "a picture inside a template: panels and chrome drawn by lp-compose (a tile column, pills, a prompt "
               "box, a compare handle, a mockup card); never a bare photo",
}


def line(e):
    """One-line summary for a brief or a skeleton."""
    if not e["basis"]:
        return "no corpus evidence for this context"
    shares = ", ".join(f"{m} {round(s * 100)} %" for m, s in sorted(e["shares"].items(), key=lambda kv: -kv[1]) if s)
    return f"**{' or '.join(e['allowed'])}** ({shares}; basis {e['basis']}, n={e['n']})"


def fits(e, family, text="none"):
    """Does a style family (with its `> text:`) make a mode this context allows?"""
    return bool(set(family_modes(family, text)) & set(e["allowed"]))
