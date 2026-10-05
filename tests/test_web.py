"""Web module files are revalidated on every load, so a deploy shows up without a hard refresh."""

from __future__ import annotations

import re


def test_web_files_are_not_cached_stale(client):
    html = client.get("/", headers={"Accept": "text/html"})
    assert html.status_code == 200 and html.headers["cache-control"] == "no-cache"
    for path in ("/js/app.js", "/js/pages/diagnose.js", "/css/app.css"):
        res = client.get(path)
        assert res.status_code == 200
        assert res.headers["cache-control"] == "no-cache"
    # An unchanged file is still cheap: the ETag revalidation answers 304.
    etag = client.get("/js/app.js").headers["etag"]
    assert client.get("/js/app.js", headers={"If-None-Match": etag}).status_code == 304


def test_every_module_url_carries_the_same_version(client):
    """index.html and every relative import use one ?v= token, so a browser holding files cached
    before no-cache existed loads the whole new module graph, never a mix of old and new files."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "web" / "public"
    tokens = set(re.findall(r'(?:app\.css|app\.js)\?v=(\d+)', (root / "index.html").read_text(encoding="utf-8")))
    for js in (root / "js").rglob("*.js"):
        for spec in re.findall(r'"(\.{1,2}/[\w/.-]+\.js[^"]*)"', js.read_text(encoding="utf-8")):
            match = re.search(r"\?v=(\d+)$", spec)
            assert match, f"{js.name}: {spec} has no ?v="
            tokens.add(match.group(1))
    assert len(tokens) == 1, tokens
