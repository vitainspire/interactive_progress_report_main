"""Heuristic textbook table-of-contents extraction.

These textbooks put their index (chapter list + page numbers) somewhere in
the first ~15 pages. Rather than scanning an entire 300-page PDF for heading
styles (fragile, and slow), we only read those first pages and pull out
lines shaped like a TOC entry: a leading chapter number, a title, and a
trailing page number — joined either by a dot leader ("3. Polynomials .... 42")
or by plain run-on spacing ("3. Polynomials   42"). Admin can review and
edit the extracted list afterward, so a few missed/garbled lines aren't
fatal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pypdf import PdfReader

TOC_SCAN_PAGES = 15
_MIN_TITLE_LEN = 3
_MAX_TITLE_LEN = 90

_DOT_LEADER_RE = re.compile(
    r"^\s*(?:chapter\s+)?(\d{1,2})[.\):]\s+(.+?)\s*[.\-–—_]{2,}\s*(\d{1,4})\s*$", re.IGNORECASE
)
_SPACED_RE = re.compile(r"^\s*(?:chapter\s+)?(\d{1,2})[.\):]\s+(.+?)\s{2,}(\d{1,4})\s*$", re.IGNORECASE)


@dataclass
class TocEntry:
    chapter_no: str
    title: str
    page: int | None


def _match_toc_line(line: str) -> tuple[str, str, str] | None:
    for pattern in (_DOT_LEADER_RE, _SPACED_RE):
        m = pattern.match(line)
        if m:
            return m.groups()
    return None


def parse_toc(pdf_path: str) -> list[TocEntry]:
    reader = PdfReader(pdf_path)
    entries: list[TocEntry] = []
    seen_titles: set[str] = set()
    for page in reader.pages[:TOC_SCAN_PAGES]:
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = _match_toc_line(line)
            if not match:
                continue
            chapter_no, title, page_no = match
            title = title.strip(" .-–—_")
            if not (_MIN_TITLE_LEN <= len(title) <= _MAX_TITLE_LEN):
                continue
            key = title.upper()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            entries.append(TocEntry(chapter_no=chapter_no, title=title, page=int(page_no) if page_no.isdigit() else None))
    return entries
