from __future__ import annotations

import html
import re

import bleach
import markdown

ALLOWED_TAGS = [
    "a",
    "article",
    "aside",
    "blockquote",
    "br",
    "code",
    "div",
    "em",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "header",
    "hr",
    "li",
    "main",
    "ol",
    "p",
    "pre",
    "section",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
]
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "*": ["class"],
}


def sanitize_html(source: str) -> str:
    source = re.sub(r"<style\b[^>]*>.*?</style>", "", source, flags=re.I | re.S)
    source = re.sub(r"<script\b[^>]*>.*?</script>", "", source, flags=re.I | re.S)
    cleaned = bleach.clean(
        source,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=["http", "https"],
        strip=True,
    )
    return cleaned


def render_artifact(format_name: str, source: str, title: str) -> str:
    if format_name == "markdown" or "<" not in source:
        body = sanitize_html(markdown.markdown(source, extensions=["extra", "sane_lists"]))
    else:
        body = sanitize_html(source)
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<title>{safe_title}</title><style>
:root{{color-scheme:light;--paper:#fffdf7;--ink:#151515;--accent:#ff5c35}}
*{{box-sizing:border-box}}body{{margin:0;padding:40px;background:var(--paper);color:var(--ink);font:16px/1.65 Georgia,serif}}
article{{max-width:760px;margin:auto}}h1,h2,h3{{line-height:1.15}}a{{color:inherit;text-decoration-color:var(--accent);text-underline-offset:3px}}
blockquote{{margin-left:0;padding-left:18px;border-left:4px solid var(--accent)}}code,pre{{font-family:ui-monospace,monospace}}pre{{overflow:auto;padding:16px;background:#f0ede4}}
</style></head><body><article>{body}</article></body></html>"""
