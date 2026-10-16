"""Allow a small set of formatting and safe links. Active content is removed."""

import re
from html.parser import HTMLParser

ALLOWED_TAGS = {
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "ul",
    "ol",
    "li",
    "a",
    "blockquote",
    "div",
    "span",
}
DROP_TAGS = {"script", "style", "iframe", "object", "svg", "math", "noscript", "template"}
SAFE_SCHEMES = ("https://", "http://", "mailto:")
VOID_TAGS = {"br"}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _safe_href(value: str) -> str | None:
    href = value.strip()
    if not href or _CONTROL.search(href) or any(mark in href for mark in ("\r", "\n", "\t")):
        return None
    lowered = href.lower()
    if lowered.startswith(SAFE_SCHEMES) and not lowered.startswith("javascript:"):
        return href
    return None


class _Cleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []

    def _dropping(self) -> bool:
        return "drop" in self.stack

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if self._dropping() or name in DROP_TAGS:
            self.stack.append("drop")
            return
        if name not in ALLOWED_TAGS:
            self.stack.append("skip")
            return
        if name == "a":
            href = _safe_href(dict(attrs).get("href") or "")
            if href is None:
                self.stack.append("skip")
                return
            self.parts.append(f'<a href="{_escape_attr(href)}">')
            self.stack.append("a")
            return
        if name not in VOID_TAGS:
            self.stack.append(name)
        self.parts.append(f"<{name}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if self._dropping() or name in DROP_TAGS or name not in ALLOWED_TAGS:
            return
        if name == "br":
            self.parts.append("<br>")

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            return
        state = self.stack.pop()
        if state in {"drop", "skip"}:
            return
        if state not in VOID_TAGS:
            self.parts.append(f"</{state}>")

    def handle_data(self, data: str) -> None:
        if self._dropping():
            return
        self.parts.append(_escape_text(data))

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")


def _escape_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(value: str) -> str:
    return _escape_text(value).replace('"', "&quot;")


def sanitize_html(value: str, *, limit: int = 8000) -> str:
    if limit < 1:
        return ""
    if len(value) > limit:
        value = value[:limit]
    cleaner = _Cleaner()
    cleaner.feed(value)
    cleaner.close()
    cleaned = "".join(cleaner.parts).strip()
    if len(cleaned) > limit:
        cleaned = cleaned[:limit]
    return cleaned


def html_to_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", sanitize_html(value, limit=100_000))
    return re.sub(r"\s+", " ", text).strip()
