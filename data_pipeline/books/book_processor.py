"""Phase 1: extract PDF text page-by-page."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from data_pipeline.common import ensure_dir, get_logger, sanitize_stem, save_json_atomic, skip_if_exists


LOGGER = get_logger(__name__)
BOOK_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BOOK_DIR / "input_books"
DEFAULT_OUTPUT_DIR = BOOK_DIR / "books_output"


def extract_pdf_pages(pdf_path: str | Path) -> list[dict[str, object]]:
    import fitz

    pdf_path = Path(pdf_path)
    pages: list[dict[str, object]] = []
    with fitz.open(pdf_path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            pages.append({"page": index, "text": text})
    return pages


def process_pdf(
    pdf_path: str | Path,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> Path | None:
    pdf_path = Path(pdf_path)
    output_dir = ensure_dir(output_dir)
    output_path = output_dir / f"{sanitize_stem(pdf_path.stem)}.json"

    if skip_if_exists(output_path, LOGGER):
        return output_path

    pages = extract_pdf_pages(pdf_path)
    if not pages or not any(str(page.get("text") or "").strip() for page in pages):
        LOGGER.warning("PDF has no extractable text: %s; skipping.", pdf_path)
        return None

    save_json_atomic(output_path, pages)
    LOGGER.info("Saved %s extracted pages to %s", len(pages), output_path)
    return output_path


def process_directory(
    *,
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    ensure_dir(output_dir)
    outputs: list[Path] = []
    for pdf_path in sorted(Path(input_dir).glob("*.pdf")):
        try:
            output = process_pdf(pdf_path, output_dir=output_dir)
            if output:
                outputs.append(output)
        except Exception as exc:
            LOGGER.exception("Failed to extract %s: %s", pdf_path, exc)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract page text from PDF books.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--file", type=Path, help="Extract one PDF file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.file:
        process_pdf(args.file, output_dir=args.output_dir)
    else:
        process_directory(input_dir=args.input_dir, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
