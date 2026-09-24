"""A composite is read back after drawing (OCR, on-device): every string a
block sets must read as the words it was given, inside the block's box."""

import pytest
import yaml
from PIL import Image

from landing_page_gen.compose import cli, verify


def test_symbols_and_numbers_must_read_exactly():
    assert verify.found("Revenue ÷ Ad Spend", "Revenue ÷ Ad Spend")
    assert not verify.found("Revenue ÷ Ad Spend", "Revenue + Ad Spend")  # the ROAS formula's 600-weight ÷
    assert not verify.found("7.14", "Your ROAS is: 7.1")
    assert verify.found("Your ROAS is:", "Your ROAS is: 7.14")


def test_a_long_word_may_differ_by_one_ocr_slip():
    assert verify.found("Facebook Ads", "• Facebok Ads")
    assert not verify.found("Facebook Ads", "• Fcebok Ads")
    assert not verify.found("Ads", "Abs")  # short words read exactly
    assert verify.found("It’s “new”", "It's \"new\"")  # typographic quotes read as straight ones


@pytest.mark.skipif(not verify.available(), reason="OCR needs macOS Vision (swiftc)")
def test_a_render_reads_back_as_its_blocks(tmp_path):
    steps = tmp_path / "steps"
    steps.mkdir()
    Image.new("RGB", (900, 1200), (230, 90, 40)).save(steps / "photo.png")
    chrome = [{"id": "card-a", "kind": "statement", "text": "Revenue ÷ Ad Spend", "rect": [232, 232, 792, 503]},
              {"id": "card-b", "kind": "list-card", "rows": ["Google Ads", "Facebook Ads"], "rect": [232, 520, 792, 983]}]
    spec = {"slot": "S04-m1", "family": "dark-composite", "preset": "bento", "size": "1600x1600",
            "panels": {"photo": {"image": "steps/photo.png"}}, "chrome": chrome}
    (tmp_path / "c.yaml").write_text(yaml.safe_dump(spec, allow_unicode=True))
    out = steps / "out.png"
    assert cli.main([str(tmp_path / "c.yaml"), "--out", str(out), "--strict"]) == 0
    assert verify.problems(out, chrome) == []
    wrong = [{**chrome[0], "text": "Revenue × Ad Spend"}]
    probs = verify.problems(out, wrong)
    assert probs and "reads 'Revenue ÷ Ad Spend'" in probs[0]
