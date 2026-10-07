"""Small text helpers shared by connectors and the classifier."""

import re
import unicodedata
from html import unescape
from html.parser import HTMLParser

_BLOCK_TAGS = {
    "p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
    "tr", "table", "section", "article", "blockquote", "pre", "hr",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "li":
            self.parts.append("\n• ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS and tag != "li":  # the next <li> starts its own line
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str | None) -> str | None:
    """Plain text from HTML, keeping paragraph breaks and list bullets."""
    if not html:
        return None
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def looks_like_html(s: str | None) -> bool:
    return bool(s) and re.search(r"<(p|br|div|li|ul|strong|b|h\d)\b", s, re.I) is not None


def clean_text(s: str | None) -> str | None:
    if not s:
        return None
    s = unescape(s).replace("\r\n", "\n").strip()
    return s or None


def fold(s: str) -> str:
    """Lowercase and strip accents: 'Bogotá' → 'bogota'."""
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def norm_key(s: str | None) -> str:
    """Normalised key for fingerprints: folded, alphanumerics only, single spaces."""
    if not s:
        return ""
    s = fold(s)
    s = re.sub(r"\b(pt|cv|tbk|inc|llc|ltd|limited|gmbh|co|corp|corporation|company)\b\.?", " ", s)
    return " ".join(re.findall(r"[a-z0-9]+", s))
