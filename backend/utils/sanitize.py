"""HTML sanitization for markdown-rendered alert email bodies.

`title`/`message` content originates from untrusted ``/shoutrrr`` ingestion
and is rendered through ``markdown.markdown()`` before being sent as an HTML
email. Markdown passes raw HTML through unchanged, so without sanitization a
notification could embed ``<script>``/``<iframe>``/event-handler attributes
that execute in the recipient's mail client.
"""

import nh3

# Tags produced by python-markdown's default extension set (headings, lists,
# emphasis, links, code blocks, tables, etc.) plus plain structural tags.
_ALLOWED_TAGS = {
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "del",
    "code",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "li",
    "a",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}

_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
}


def sanitize_html(html: str) -> str:
    """Strip any tags/attributes not needed for basic alert email formatting.

    Removes script/style/iframe/event-handler content entirely while
    preserving the basic formatting markdown produces.
    """
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer",
    )
