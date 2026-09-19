"""save_page sources its HTML from the hydrated browser DOM (the pages stream
their content as RSC script payloads, so the served body is empty), and treats a
client-redirect to /not-found/ as a shell."""
import json

from landing_page_gen.corpus import snapshot


class StubRenderer:
    """Stands in for the Chromium Renderer: returns a fixed (geometry, html,
    final_url) and writes a dummy png, exactly like the real one."""
    def __init__(self, html, final_url):
        self.html, self.final_url = html, final_url

    def render(self, url, png_path):
        png_path.write_bytes(b"\x89PNG\r\n")   # a stand-in screenshot
        return [{"slot": "S01"}], self.html, self.final_url


REAL = ("<html><head><title>Unblur Image - Picsart</title></head><body>"
        "<main><h1>Unblur images</h1><p>" + "Remove blur from your photos with the AI unblur tool. " * 8 +
        "</p></main></body></html>")


def test_rendered_dom_becomes_the_snapshot(tmp_path):
    d = snapshot.save_page("https://picsart.com/ai-image-enhancer/unblur/",
                           pages_dir=tmp_path, renderer=StubRenderer(REAL, "https://picsart.com/ai-image-enhancer/unblur/"),
                           localise=False, log=lambda m: None)
    meta = json.loads((d / "meta.json").read_text())
    assert not meta.get("shell") and meta.get("rendered") is True
    page = (d / "page.html").read_text()
    assert "Unblur images" in page and "<script" not in page   # snapshot is script-free
    assert (d / "page.png").exists() and (d / "render.json").exists()


def test_a_client_redirect_to_not_found_is_a_shell(tmp_path):
    # a dead route: the browser lands on /not-found/, whose page has plenty of
    # text, so only the final-URL guard catches it
    d = snapshot.save_page("https://picsart.com/ai-image-generator/anime/",
                           pages_dir=tmp_path, renderer=StubRenderer(REAL, "https://picsart.com/not-found/"),
                           localise=False, log=lambda m: None)
    meta = json.loads((d / "meta.json").read_text())
    assert meta.get("shell") is True
    assert not (d / "page.html").exists()
    assert not (d / "page.png").exists()   # the misleading not-found screenshot is dropped
