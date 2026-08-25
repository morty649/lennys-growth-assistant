from app.artifacts import render_artifact, sanitize_html


def test_html_artifacts_strip_active_content() -> None:
    source = '<script>alert(1)</script><p onclick="alert(2)">Safe</p><iframe src="x"></iframe>'
    cleaned = sanitize_html(source)

    assert "script" not in cleaned
    assert "onclick" not in cleaned
    assert "iframe" not in cleaned
    assert "Safe" in cleaned


def test_rendered_artifact_is_a_complete_document() -> None:
    rendered = render_artifact("markdown", "# Grounded brief", "Brief")

    assert rendered.startswith("<!doctype html>")
    assert "<h1>Grounded brief</h1>" in rendered


def test_plain_html_artifact_source_renders_markdown_links() -> None:
    rendered = render_artifact("html", "[Source](https://example.com)", "Brief")

    assert '<a href="https://example.com">Source</a>' in rendered
    assert "[Source](" not in rendered
