# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from bs4 import BeautifulSoup

from plane.utils.attachment_html_preview import sanitize_html_attachment_preview


def test_sanitize_html_attachment_preview_keeps_static_content_only():
    html = b"""
        <!doctype html>
        <html>
          <head>
            <base href="https://tracker.example/">
            <link rel="stylesheet" href="https://tracker.example/style.css">
            <meta http-equiv="refresh" content="0;https://tracker.example/">
            <style>
              h1 { color: red; }
              body { background-image: url("https://css-tracker.example/pixel.png"); }
            </style>
            <script>window.top.location = "https://tracker.example/"</script>
          </head>
          <body onload="alert(1)">
            <h1>Quarterly report</h1>
            <a
              href="https://tracker.example/"
              ping="https://tracker.example/ping"
              style="background: url(javascript:alert(1)); color: red"
            >Open</a>
            <form action="https://tracker.example/submit"><p>Form label</p><input name="secret"></form>
            <iframe src="https://tracker.example/frame"></iframe>
            <object data="https://tracker.example/object"></object>
            <embed src="https://tracker.example/embed">
            <img id="remote" src="https://tracker.example/pixel.png">
            <img id="embedded" src="data:image/png;base64,AAAA">
            <svg><a xlink:href="https://tracker.example/svg">SVG link</a></svg>
          </body>
        </html>
    """

    sanitized = sanitize_html_attachment_preview(html)
    soup = BeautifulSoup(sanitized, "html.parser")

    assert soup.find("h1").get_text(strip=True) == "Quarterly report"
    assert soup.find("style") is not None
    assert soup.find("script") is None
    assert soup.find("iframe") is None
    assert soup.find("object") is None
    assert soup.find("embed") is None
    assert soup.find("base") is None
    assert soup.find("link") is None
    assert soup.find("meta", attrs={"http-equiv": "refresh"}) is None
    assert soup.find("form") is None
    assert soup.find("input") is None
    assert soup.find(string="Form label") is not None
    assert soup.find("body").get("onload") is None
    assert soup.find("a").get("href") is None
    assert soup.find("a").get("ping") is None
    assert soup.find("svg").find("a").get("xlink:href") is None
    assert soup.find("img", id="remote").get("src") is None
    assert soup.find("img", id="embedded").get("src") == "data:image/png;base64,AAAA"
    assert "css-tracker.example" not in sanitized
    assert "javascript:" not in sanitized


def test_sanitize_html_attachment_preview_honors_declared_encoding():
    html = '<meta charset="gb18030"><h1>季度报告</h1>'.encode("gb18030")

    sanitized = sanitize_html_attachment_preview(html)

    assert "季度报告" in sanitized
