"""Tests for utils.sanitize.sanitize_html — used to scrub HTML produced by
``markdown.markdown()`` from untrusted notification title/message content
before it is sent as an alert email body."""

from utils.sanitize import sanitize_html


def test_strips_script_tags():
    html = "<p>Hello</p><script>alert('xss')</script>"
    result = sanitize_html(html)
    assert "<script" in html
    assert "<script" not in result
    assert "alert" not in result


def test_strips_event_handler_attributes():
    html = '<img src="x" onerror="alert(1)"><p>text</p>'
    result = sanitize_html(html)
    assert "onerror" not in result
    assert "<p>text</p>" in result


def test_strips_javascript_href():
    html = '<a href="javascript:alert(1)">click me</a>'
    result = sanitize_html(html)
    assert "javascript:" not in result


def test_strips_iframe():
    html = '<iframe src="https://evil.example.com"></iframe><p>ok</p>'
    result = sanitize_html(html)
    assert "<iframe" not in result
    assert "<p>ok</p>" in result


def test_preserves_basic_markdown_formatting():
    html = '<p>Hello <strong>world</strong>, see <a href="https://example.com">this</a></p>'
    result = sanitize_html(html)
    assert "<strong>world</strong>" in result
    assert 'href="https://example.com"' in result


def test_preserves_lists_and_code_blocks():
    html = "<ul><li>one</li><li>two</li></ul><pre><code>print(1)</code></pre>"
    result = sanitize_html(html)
    assert "<li>one</li>" in result
    assert "<pre><code>print(1)</code></pre>" in result
