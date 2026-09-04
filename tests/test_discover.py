from landing_page_gen.corpus import discover as d


def test_normalize_keeps_landing_paths_only():
    assert d.normalize("/ai-models/flux-3/") == "/ai-models/flux-3/"
    assert d.normalize("https://picsart.com/persona") == "/persona/"
    assert d.normalize("/ai-playground/?model=flux-3") is None      # query + skipped prefix
    assert d.normalize("/es_es/ai-models/flux-3/") is None          # locale
    assert d.normalize("/blog/some-post/") is None                  # skipped prefix
    assert d.normalize("https://twitter.com/picsart") is None       # off-host
    assert d.normalize("#faq") is None


def test_classify_families():
    assert d.classify("/ai-models/") == "hub"
    assert d.classify("/video-models/") == "hub"
    assert d.normalize("/community-guidelines/") is None
    assert d.classify("/ai-models/seedance-2-5/") == "ai-models"
    assert d.classify("/compare-models/seedance-2-5-vs-kling-3-0/") == "compare-models"
    assert d.classify("/comic-book-generator/") == "tool"
    assert d.classify("/background-remover/") == "tool"
    assert d.classify("/ai-image-generator/") == "tool"
    assert d.classify("/ai-agents/") == "ai-tool"
    assert d.classify("/persona/") == "other"
    assert d.classify("/ai-models/flux-3/specs/") is None


def test_parse_extracts_title_and_links():
    html = '<html><head><title>Flux 3 | Picsart</title></head><body>' \
           '<a href="/ai-models/kling-3-0/">k</a><a href="/blog/x/">b</a>' \
           '<a href="https://picsart.com/persona">p</a></body></html>'
    title, links = d.parse(html)
    assert title == "Flux 3 | Picsart"
    assert links == {"/ai-models/kling-3-0/", "/persona/"}
