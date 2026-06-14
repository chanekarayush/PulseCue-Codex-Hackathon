"""Extract first-page thumbnails from PDF books."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from data_pipeline.common import ensure_dir, get_logger, sanitize_stem, skip_if_exists


LOGGER = get_logger(__name__)
BOOK_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BOOK_DIR / "input_books"
DEFAULT_OUTPUT_DIR = BOOK_DIR / "book_thumbnails"


def extract_thumbnail(
    pdf_path: str | Path,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    zoom: float = 1.6,
) -> Path | None:
    import fitz

    pdf_path = Path(pdf_path)
    output_dir = ensure_dir(output_dir)
    output_path = output_dir / f"{sanitize_stem(pdf_path.stem)}.png"
    if skip_if_exists(output_path, LOGGER):
        return output_path

    with fitz.open(pdf_path) as document:
        if document.page_count == 0:
            LOGGER.warning("PDF has no pages: %s; skipping thumbnail.", pdf_path)
            return None
        page = document.load_page(0)
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        pixmap.save(output_path)

    LOGGER.info("Saved thumbnail to %s", output_path)
    return output_path


def extract_directory(
    *,
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    outputs: list[Path] = []
    for pdf_path in sorted(Path(input_dir).glob("*.pdf")):
        try:
            output = extract_thumbnail(pdf_path, output_dir=output_dir)
            if output:
                outputs.append(output)
        except Exception as exc:
            LOGGER.exception("Failed to extract thumbnail from %s: %s", pdf_path, exc)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract first-page PDF thumbnails.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--file", type=Path, help="Extract one PDF thumbnail.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.file:
        extract_thumbnail(args.file, output_dir=args.output_dir)
    else:
        extract_directory(input_dir=args.input_dir, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
