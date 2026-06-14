"""Master script to run all three book pipeline phases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from data_pipeline.books.book_chunk_processor import process_directory as chunk_books
from data_pipeline.books.book_enricher import enrich_directory
from data_pipeline.books.book_processor import process_directory as extract_books


BOOK_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = BOOK_DIR / "input_books"
DEFAULT_OUTPUT_DIR = BOOK_DIR / "books_output"
DEFAULT_METADATA_DIR = BOOK_DIR / "books_enriched_metadata"
DEFAULT_CHUNKS_DIR = BOOK_DIR / "processed_books_chunks"


def run_book_pipeline(
    *,
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
    chunks_dir: str | Path = DEFAULT_CHUNKS_DIR,
    skip_enrichment: bool = False,
    skip_chunking: bool = False,
) -> None:
    extract_books(input_dir=input_dir, output_dir=output_dir)
    if not skip_enrichment:
        enrich_directory(input_dir=output_dir, output_dir=metadata_dir)
    if not skip_chunking:
        chunk_books(input_dir=output_dir, output_dir=chunks_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full book pipeline.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("--skip-enrichment", action="store_true")
    parser.add_argument("--skip-chunking", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_book_pipeline(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        metadata_dir=args.metadata_dir,
        chunks_dir=args.chunks_dir,
        skip_enrichment=args.skip_enrichment,
        skip_chunking=args.skip_chunking,
    )


if __name__ == "__main__":
    main()
