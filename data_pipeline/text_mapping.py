"""Character offset mapping utilities for videos and books."""

from __future__ import annotations

import bisect
import re
import string
from dataclasses import dataclass
from typing import Any, Sequence


EXTRA_PUNCTUATION = "।॥“”‘’…–—"
PUNCTUATION = string.punctuation + EXTRA_PUNCTUATION


@dataclass(frozen=True)
class CharTimeSpan:
    start_char: int
    end_char: int
    start_time: float
    duration: float
    text_len: int


@dataclass(frozen=True)
class CharPageSpan:
    start_char: int
    end_char: int
    page: int


@dataclass(frozen=True)
class TextMatch:
    start: int
    end: int
    matched_text: str
    strategy: str


def build_video_text_and_time_map(
    fragments: Sequence[dict[str, Any]],
    *,
    separator: str = " ",
) -> tuple[str, list[CharTimeSpan]]:
    """Concatenate transcript fragments and map every text span to timestamps."""

    parts: list[str] = []
    spans: list[CharTimeSpan] = []
    current_char = 0

    for fragment in fragments:
        text = str(fragment.get("text") or "").strip()
        if not text:
            continue

        if parts:
            current_char += len(separator)
        start_char = current_char
        text_len = len(text)
        end_char = start_char + text_len

        spans.append(
            CharTimeSpan(
                start_char=start_char,
                end_char=end_char,
                start_time=float(fragment.get("start_time", fragment.get("start", 0.0)) or 0.0),
                duration=float(fragment.get("duration", 0.0) or 0.0),
                text_len=text_len,
            )
        )
        parts.append(text)
        current_char = end_char

    return separator.join(parts), spans


def build_book_text_and_page_map(
    pages: Sequence[dict[str, Any]],
    *,
    separator: str = "\n\n",
) -> tuple[str, list[CharPageSpan]]:
    """Concatenate page text and map character spans back to page numbers."""

    parts: list[str] = []
    spans: list[CharPageSpan] = []
    current_char = 0

    for page_obj in pages:
        text = str(page_obj.get("text") or "").strip()
        if not text:
            continue

        if parts:
            current_char += len(separator)
        start_char = current_char
        end_char = start_char + len(text)
        spans.append(
            CharPageSpan(
                start_char=start_char,
                end_char=end_char,
                page=int(page_obj.get("page") or len(spans) + 1),
            )
        )
        parts.append(text)
        current_char = end_char

    return separator.join(parts), spans


def resolve_time_from_char_index(char_index: int, spans: Sequence[CharTimeSpan]) -> float | None:
    """Resolve an absolute character offset to an interpolated video timestamp."""

    if not spans:
        return None

    safe_index = max(0, char_index)
    starts = [span.start_char for span in spans]
    span_index = bisect.bisect_right(starts, safe_index) - 1

    if span_index < 0:
        return spans[0].start_time

    span = spans[span_index]
    if safe_index >= span.end_char:
        if span_index + 1 < len(spans):
            return spans[span_index + 1].start_time
        safe_index = span.end_char - 1

    chars_into_fragment = min(max(safe_index - span.start_char, 0), max(span.text_len, 1))
    ratio = chars_into_fragment / max(span.text_len, 1)
    return span.start_time + (span.duration * ratio)


def resolve_page_from_char_index(char_index: int, spans: Sequence[CharPageSpan]) -> int | None:
    """Resolve an absolute character offset to the containing/nearest page."""

    if not spans:
        return None

    safe_index = max(0, char_index)
    starts = [span.start_char for span in spans]
    span_index = bisect.bisect_right(starts, safe_index) - 1

    if span_index < 0:
        return spans[0].page

    span = spans[span_index]
    if safe_index >= span.end_char and span_index + 1 < len(spans):
        return spans[span_index + 1].page
    return span.page


def find_text_span(haystack: str, needle: str, *, start: int = 0) -> TextMatch | None:
    """Find exact text first, then tolerate punctuation/whitespace drift."""

    if not haystack or not needle or not needle.strip():
        return None

    exact_index = haystack.find(needle, max(0, start))
    if exact_index >= 0:
        return TextMatch(
            start=exact_index,
            end=exact_index + len(needle),
            matched_text=haystack[exact_index : exact_index + len(needle)],
            strategy="exact",
        )

    compact_needle = " ".join(needle.split())
    if compact_needle != needle:
        compact_index = haystack.find(compact_needle, max(0, start))
        if compact_index >= 0:
            return TextMatch(
                start=compact_index,
                end=compact_index + len(compact_needle),
                matched_text=haystack[compact_index : compact_index + len(compact_needle)],
                strategy="normalized_whitespace",
            )

    tokens = [token.strip(PUNCTUATION) for token in compact_needle.split()]
    tokens = [token for token in tokens if token]
    if not tokens:
        return None

    pattern = r"[\s\W_]+".join(re.escape(token) for token in tokens)
    match = re.search(pattern, haystack[max(0, start) :], flags=re.IGNORECASE | re.UNICODE)
    if not match:
        return None

    absolute_start = max(0, start) + match.start()
    absolute_end = max(0, start) + match.end()
    return TextMatch(
        start=absolute_start,
        end=absolute_end,
        matched_text=haystack[absolute_start:absolute_end],
        strategy="punctuation_regex",
    )


def resolve_segment_timestamps(
    segment: dict[str, Any],
    full_text: str,
    spans: Sequence[CharTimeSpan],
) -> dict[str, Any]:
    """Attach zero-drift timestamps to one LLM-extracted video segment."""

    enriched = dict(segment)
    start_text = str(segment.get("exact_start_text") or "").strip()
    end_text = str(segment.get("exact_end_text") or "").strip()

    if not start_text:
        enriched["timestamp_resolution"] = {
            "status": "unresolved",
            "reason": "missing exact_start_text",
        }
        return enriched

    start_match = find_text_span(full_text, start_text)
    if not start_match:
        enriched["timestamp_resolution"] = {
            "status": "unresolved",
            "reason": "exact_start_text not found",
            "exact_start_text": start_text,
        }
        return enriched

    end_match = find_text_span(full_text, end_text, start=start_match.start) if end_text else None
    start_time = resolve_time_from_char_index(start_match.start, spans)
    end_time = None
    if end_match:
        end_time = resolve_time_from_char_index(max(end_match.end - 1, end_match.start), spans)

    enriched.update(
        {
            "start_time": start_time,
            "end_time": end_time,
            "start_char": start_match.start,
            "end_char": end_match.end if end_match else None,
            "timestamp_resolution": {
                "status": "resolved" if start_time is not None else "unresolved",
                "start_match_strategy": start_match.strategy,
                "end_match_strategy": end_match.strategy if end_match else None,
                "matched_start_text": start_match.matched_text,
                "matched_end_text": end_match.matched_text if end_match else None,
            },
        }
    )
    return enriched

