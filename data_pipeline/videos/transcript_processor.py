"""Phase 3: semantic video chunks with zero-drift timestamp mapping."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from data_pipeline.common import (
    ensure_dir,
    get_logger,
    iter_json_files,
    load_json,
    save_json_atomic,
    skip_if_exists,
)
from data_pipeline.splitters import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, split_text_with_start_indices
from data_pipeline.text_mapping import build_video_text_and_time_map, resolve_time_from_char_index


LOGGER = get_logger(__name__)
VIDEO_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = VIDEO_DIR / "output"
DEFAULT_OUTPUT_DIR = VIDEO_DIR / "processed_chunks"


def process_transcript_file(
    transcript_path: str | Path,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Path | None:
    transcript_path = Path(transcript_path)
    output_dir = ensure_dir(output_dir)
    video_id = transcript_path.stem
    output_path = output_dir / f"{video_id}_chunks.json"

    if skip_if_exists(output_path, LOGGER):
        return output_path

    fragments = load_json(transcript_path)
    if not fragments:
        LOGGER.warning("Transcript file is empty: %s; skipping chunking.", transcript_path)
        return None

    full_text, char_to_time_map = build_video_text_and_time_map(fragments)
    if not full_text.strip() or not char_to_time_map:
        LOGGER.warning("Transcript has no usable text: %s; skipping chunking.", transcript_path)
        return None

    split_chunks = split_text_with_start_indices(
        full_text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = []
    for index, chunk in enumerate(split_chunks):
        start_time = resolve_time_from_char_index(chunk.start_index, char_to_time_map)
        end_time = resolve_time_from_char_index(max(chunk.end_index - 1, chunk.start_index), char_to_time_map)
        chunks.append(
            {
                "chunk_id": f"{video_id}_{index:04d}",
                "video_id": video_id,
                "source_type": "youtube_video",
                "text": chunk.text,
                "start_index": chunk.start_index,
                "end_index": chunk.end_index,
                "start_time": start_time,
                "end_time": end_time,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            }
        )

    save_json_atomic(output_path, chunks)
    LOGGER.info("Saved %s video chunks to %s", len(chunks), output_path)
    return output_path


def process_directory(
    *,
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Path]:
    ensure_dir(output_dir)
    outputs: list[Path] = []
    for transcript_path in iter_json_files(input_dir):
        try:
            output = process_transcript_file(
                transcript_path,
                output_dir=output_dir,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if output:
                outputs.append(output)
        except Exception as exc:
            LOGGER.exception("Failed to process %s: %s", transcript_path, exc)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create timestamped video chunks for Qdrant.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--file", type=Path, help="Process one transcript JSON file.")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.file:
        process_transcript_file(
            args.file,
            output_dir=args.output_dir,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    else:
        process_directory(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )


if __name__ == "__main__":
    main()
