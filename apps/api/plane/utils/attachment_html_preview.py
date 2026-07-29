# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import re

from bs4 import BeautifulSoup


_REMOVED_TAGS = {
    "applet",
    "base",
    "embed",
    "frame",
    "frameset",
    "iframe",
    "link",
    "object",
    "script",
}
_REMOVED_CONTROLS = {"button", "input", "select", "textarea"}
_NAVIGATION_ATTRIBUTES = {
    "action",
    "archive",
    "background",
    "cite",
    "classid",
    "code",
    "codebase",
    "data",
    "formaction",
    "href",
    "longdesc",
    "manifest",
    "ping",
    "poster",
    "profile",
    "src",
    "srcdoc",
    "srcset",
    "usemap",
}
_ALLOWED_DATA_IMAGE = re.compile(
    r"^data:image/(?:png|jpe?g|gif|webp);base64,[a-z0-9+/=\s]+$",
    flags=re.IGNORECASE,
)
_ALLOWED_CSS_DATA_URL = re.compile(
    r"^data:(?:image/(?:png|jpe?g|gif|webp)|font/(?:otf|ttf|woff2?));base64,[a-z0-9+/=\s]+$",
    flags=re.IGNORECASE,
)
_CSS_IMPORT = re.compile(r"@import\s+[^;]*(?:;|$)", flags=re.IGNORECASE)
_CSS_URL = re.compile(
    r"url\s*\(\s*(?P<quote>['\"]?)(?P<value>.*?)(?P=quote)\s*\)",
    flags=re.IGNORECASE | re.DOTALL,
)


def _sanitize_inline_css(value: str) -> str:
    # CSS escapes can obfuscate url()/@import tokens. Dropping escaped CSS is
    # deliberately conservative for a static, untrusted preview.
    if "\\" in value:
        return ""

    without_imports = _CSS_IMPORT.sub("", value)

    def replace_url(match: re.Match) -> str:
        url = match.group("value").strip()
        if _ALLOWED_CSS_DATA_URL.fullmatch(url):
            return f'url("{url}")'
        return "none"

    return _CSS_URL.sub(replace_url, without_imports)


def sanitize_html_attachment_preview(content: bytes) -> str:
    """Return a static-only HTML representation suitable for sandboxed preview."""

    soup = BeautifulSoup(content, "html.parser")

    for tag_name in _REMOVED_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for meta in soup.find_all("meta"):
        http_equiv = meta.get("http-equiv")
        if isinstance(http_equiv, str) and http_equiv.strip().lower() == "refresh":
            meta.decompose()

    for style in soup.find_all("style"):
        css = style.string
        if css is None:
            style.clear()
            continue
        css.replace_with(_sanitize_inline_css(str(css)))

    for form in soup.find_all("form"):
        form.unwrap()

    for tag_name in _REMOVED_CONTROLS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for tag in soup.find_all(True):
        for attribute_name in list(tag.attrs):
            normalized_name = attribute_name.lower()
            if normalized_name.startswith("on"):
                del tag.attrs[attribute_name]
                continue

            if normalized_name == "style":
                value = tag.attrs.get(attribute_name)
                if isinstance(value, str):
                    tag.attrs[attribute_name] = _sanitize_inline_css(value)
                else:
                    del tag.attrs[attribute_name]
                continue

            if normalized_name not in _NAVIGATION_ATTRIBUTES and not normalized_name.endswith(":href"):
                continue

            value = tag.attrs.get(attribute_name)
            if (
                tag.name == "img"
                and normalized_name == "src"
                and isinstance(value, str)
                and _ALLOWED_DATA_IMAGE.fullmatch(value.strip())
            ):
                continue

            del tag.attrs[attribute_name]

    return str(soup)
