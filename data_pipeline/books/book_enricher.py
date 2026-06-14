"""Phase 2: enrich extracted books using smart LLM sampling."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from data_pipeline.common import (
    ensure_dir,
    extract_json_object,
    get_logger,
    iter_json_files,
    load_json,
    save_json_atomic,
    skip_if_exists,
)
from data_pipeline.llm_client import LLMClient


LOGGER = get_logger(__name__)
BOOK_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BOOK_DIR / "books_output"
DEFAULT_OUTPUT_DIR = BOOK_DIR / "books_enriched_metadata"


FIRST_SAMPLE_CHARS = 40_000
MIDDLE_SAMPLE_CHARS = 8_000
FINAL_SAMPLE_CHARS = 8_000


BOOK_SYSTEM_PROMPT = """
You are Ditto's expert metadata extractor for spiritual books. You will receive a
smart sample from a PDF: the beginning, middle, and end joined by [...] markers.
Return only a valid JSON object. Do not include markdown, code fences, or prose.

JSON schema:
{
  "title": "string|null",
  "author": "string|null",
  "date_written": "string|null",
  "summary": "string",
  "questions": ["8-10 core questions the book answers"],
  "key_learnings": ["string"],
  "for_whom": ["string"],
  "mood": ["string"],
  "topics": ["string"],
  "structure_type": "linear|commentary|dialogue|sermons|poetry|qa|mixed|unknown",
  "table_of_contents": [
    {"section": "string", "page_hint": "number|null", "description": "string"}
  ]
}

Rules:
1. Use null when the sample does not support a field.
2. Reconstruct table_of_contents only from visible evidence or clear structure.
3. Keep questions practical and search-oriented.
4. Preserve names/titles from the source language where appropriate.
""".strip()


def concatenate_pages(pages: list[dict[str, Any]]) -> str:
    parts = []
    for page in pages:
        text = str(page.get("text") or "").strip()
        if text:
            parts.append(f"[Page {page.get('page')}]\n{text}")
    return "\n\n".join(parts)


def smart_sample_text(
    text: str,
    *,
    first_chars: int = FIRST_SAMPLE_CHARS,
    middle_chars: int = MIDDLE_SAMPLE_CHARS,
    final_chars: int = FINAL_SAMPLE_CHARS,
) -> str:
    if len(text) <= first_chars + middle_chars + final_chars:
        return text

    first = text[:first_chars]
    middle_start = max(first_chars, (len(text) - middle_chars) // 2)
    middle_end = min(len(text) - final_chars, middle_start + middle_chars)
    middle = text[middle_start:middle_end]
    final = text[-final_chars:]
    return "\n\n[...]\n\n".join([first, middle, final])


def enrich_book_file(
    pages_path: str | Path,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    llm_client: LLMClient | None = None,
) -> Path | None:
    pages_path = Path(pages_path)
    output_dir = ensure_dir(output_dir)
    book_name = pages_path.stem
    output_path = output_dir / f"{book_name}_meta.json"

    if skip_if_exists(output_path, LOGGER):
        return output_path

    pages = load_json(pages_path)
    if not pages:
        LOGGER.warning("Book extraction JSON is empty: %s; skipping enrichment.", pages_path)
        return None

    full_text = concatenate_pages(pages)
    if not full_text.strip():
        LOGGER.warning("Book has no usable text: %s; skipping enrichment.", pages_path)
        return None

    sampled_text = smart_sample_text(full_text)
    client = llm_client or LLMClient()
    raw_response = client.generate_json_text(
        system_prompt=BOOK_SYSTEM_PROMPT,
        user_text=sampled_text,
    )
    parsed = extract_json_object(raw_response)
    parsed.update(
        {
            "book_id": book_name,
            "source_type": "pdf_book",
            "full_text_char_count": len(full_text),
            "sample_char_count": len(sampled_text),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    save_json_atomic(output_path, parsed)
    LOGGER.info("Saved book metadata to %s", output_path)
    return output_path


def enrich_directory(
    *,
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    ensure_dir(output_dir)
    client = LLMClient()
    outputs: list[Path] = []
    for pages_path in iter_json_files(input_dir):
        try:
            output = enrich_book_file(pages_path, output_dir=output_dir, llm_client=client)
            if output:
                outputs.append(output)
        except Exception as exc:
            LOGGER.exception("Failed to enrich %s: %s", pages_path, exc)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich extracted book text with LLM metadata.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--file", type=Path, help="Process one extracted book JSON file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.file:
        enrich_book_file(args.file, output_dir=args.output_dir)
    else:
        enrich_directory(input_dir=args.input_dir, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
