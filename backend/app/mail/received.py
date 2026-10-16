"""Display received mail with safe formatting, isolated from compose/signature policy."""

import re

import nh3

TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "br",
    "caption",
    "center",
    "code",
    "col",
    "colgroup",
    "dd",
    "del",
    "div",
    "dl",
    "dt",
    "em",
    "font",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "samp",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
STYLES = {
    "background-color",
    "border",
    "border-bottom",
    "border-bottom-color",
    "border-bottom-style",
    "border-bottom-width",
    "border-collapse",
    "border-color",
    "border-left",
    "border-left-color",
    "border-left-style",
    "border-left-width",
    "border-radius",
    "border-right",
    "border-right-color",
    "border-right-style",
    "border-right-width",
    "border-spacing",
    "border-style",
    "border-top",
    "border-top-color",
    "border-top-style",
    "border-top-width",
    "border-width",
    "color",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "height",
    "letter-spacing",
    "line-height",
    "list-style-type",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-height",
    "max-width",
    "min-width",
    "overflow-wrap",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "text-align",
    "text-decoration",
    "text-indent",
    "text-transform",
    "vertical-align",
    "white-space",
    "width",
    "word-break",
}
_DIMENSION = re.compile(r"\d{1,4}%?\Z")


def _attribute(tag: str, name: str, value: str) -> str | None:
    if name == "href":
        # Permit explicit web/mail links, never relative URLs or data/script URLs.
        if not value.lower().startswith(("https://", "http://", "mailto:")):
            return None
    if name in {"width", "height", "cellpadding", "cellspacing", "border"}:
        if not _DIMENSION.fullmatch(value.strip()):
            return None
        if int(value.strip().rstrip("%")) > (100 if value.strip().endswith("%") else 4096):
            return None
    if name in {"colspan", "rowspan"}:
        if not value.isdecimal() or not 1 <= int(value) <= 100:
            return None
    return value


_CLEANER = nh3.Cleaner(
    tags=TAGS,
    clean_content_tags={
        "script",
        "style",
        "iframe",
        "object",
        "embed",
        "svg",
        "math",
        "noscript",
        "template",
        "form",
        "button",
        "select",
        "textarea",
        "title",
    },
    attributes={
        "*": {"style", "title", "dir", "lang"},
        "a": {"href"},
        "table": {"width", "height", "border", "cellpadding", "cellspacing", "align", "bgcolor"},
        "td": {"width", "height", "colspan", "rowspan", "align", "valign", "bgcolor"},
        "th": {"width", "height", "colspan", "rowspan", "align", "valign", "bgcolor", "scope"},
        "tr": {"align", "valign", "bgcolor"},
        "col": {"width", "span"},
        "font": {"color", "size", "face"},
        "p": {"align"},
        "div": {"align"},
        "ol": {"start", "type"},
        "li": {"value"},
    },
    attribute_filter=_attribute,
    filter_style_properties=STYLES,
    url_schemes={"http", "https", "mailto"},
    url_relative="deny",
    link_rel="noopener noreferrer",
)


def received_html(value: str, *, limit: int) -> str:
    """Never unescape message text: quoted HTML in a technical email is literal text."""
    if limit < 1:
        return ""
    cleaned = _CLEANER.clean(value[:limit])
    if len(cleaned) > limit:
        return "<p>This message is too large to display here. It remains in your mailbox.</p>"
    return cleaned
