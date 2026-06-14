"""Phase 2: enrich transcripts with LLM metadata and zero-drift timestamps."""

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
from data_pipeline.text_mapping import (
    CharTimeSpan,
    build_video_text_and_time_map,
    resolve_segment_timestamps,
)


LOGGER = get_logger(__name__)
VIDEO_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = VIDEO_DIR / "output"
DEFAULT_OUTPUT_DIR = VIDEO_DIR / "enriched_metadata"


VIDEO_SYSTEM_PROMPT = """
You are Ditto's expert metadata extractor for English motivation and fitness
videos. You will receive a full YouTube transcript. Return only a valid JSON
object. Do not include markdown, code fences, or explanatory text.

JSON schema:
{
  "title_suggestion": "string",
  "summary": "string",
  "target_audience": ["string"],
  "difficulty_level": "beginner|intermediate|advanced|mixed|unknown",
  "topics": ["string"],
  "queries_solved": [
    {
      "query": "A search-style question solved in the video",
      "answer": "Concise answer from the transcript",
      "exact_start_text": "The first 7-10 words of the answered segment copied verbatim",
      "exact_end_text": "The last 7-10 words of the answered segment copied verbatim"
    }
  ],
  "experiences": [
    {
      "title": "string",
      "experience_type": "personal_experience|client_transformation|failure_lesson|mindset_shift|other",
      "summary": "string",
      "lesson": "string",
      "exact_start_text": "The first 7-10 words of the experience segment copied verbatim",
      "exact_end_text": "The last 7-10 words of the experience segment copied verbatim"
    }
  ],
  "fitness_advice": [
    {
      "advice": "string",
      "category": "training|nutrition|recovery|mobility|fat_loss|muscle_gain|habit|mindset|safety|other",
      "why_it_matters": "string",
      "how_to_apply": "string",
      "exact_start_text": "The first 7-10 words of the advice segment copied verbatim",
      "exact_end_text": "The last 7-10 words of the advice segment copied verbatim"
    }
  ],
  "motivational_takeaways": [
    {"takeaway": "string", "context": "string"}
  ]
}

Critical rules:
1. exact_start_text and exact_end_text must be copied verbatim from the transcript.
2. Do not invent timestamps; the pipeline resolves timestamps from exact text anchors.
3. Ignore audio-only, performance-only, or unrelated legacy metadata.
4. Prefer practical fitness/motivation search intent over generic summaries.
5. Use empty arrays when the transcript does not support a field.
6. Keep JSON keys exactly as specified.
""".strip()


def _resolve_timestamps(
    metadata: dict[str, Any],
    full_text: str,
    char_to_time_map: list[CharTimeSpan],
) -> dict[str, Any]:
    """Resolve anchored fitness/motivation metadata to interpolated transcript times."""

    resolved = dict(metadata)
    for key in ("experiences", "fitness_advice", "queries_solved"):
        value = resolved.get(key)
        if isinstance(value, list):
            resolved[key] = [
                resolve_segment_timestamps(segment, full_text, char_to_time_map)
                if isinstance(segment, dict)
                else segment
                for segment in value
            ]
    return resolved


def enrich_transcript_file(
    transcript_path: str | Path,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    llm_client: LLMClient | None = None,
) -> Path | None:
    transcript_path = Path(transcript_path)
    output_dir = ensure_dir(output_dir)
    video_id = transcript_path.stem
    output_path = output_dir / f"{video_id}_meta.json"

    if skip_if_exists(output_path, LOGGER):
        return output_path

    fragments = load_json(transcript_path)
    if not fragments:
        LOGGER.warning("Transcript file is empty: %s; skipping enrichment.", transcript_path)
        return None

    full_text, char_to_time_map = build_video_text_and_time_map(fragments)
    if not full_text.strip() or not char_to_time_map:
        LOGGER.warning("Transcript has no usable text: %s; skipping enrichment.", transcript_path)
        return None

    client = llm_client or LLMClient()
    raw_response = client.generate_json_text(
        system_prompt=VIDEO_SYSTEM_PROMPT,
        user_text=full_text,
    )
    parsed = extract_json_object(raw_response)
    resolved = _resolve_timestamps(parsed, full_text, char_to_time_map)
    resolved.update(
        {
            "video_id": video_id,
            "source_type": "youtube_video",
            "transcript_char_count": len(full_text),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    save_json_atomic(output_path, resolved)
    LOGGER.info("Saved enriched metadata to %s", output_path)
    return output_path


def enrich_directory(
    *,
    input_dir: str | Path = DEFAULT_INPUT_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    ensure_dir(output_dir)
    client = LLMClient()
    outputs: list[Path] = []
    for transcript_path in iter_json_files(input_dir):
        try:
            output = enrich_transcript_file(
                transcript_path,
                output_dir=output_dir,
                llm_client=client,
            )
            if output:
                outputs.append(output)
        except Exception as exc:
            LOGGER.exception("Failed to enrich %s: %s", transcript_path, exc)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich video transcripts with LLM metadata.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--file", type=Path, help="Process one transcript JSON file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.file:
        enrich_transcript_file(args.file, output_dir=args.output_dir)
    else:
        enrich_directory(input_dir=args.input_dir, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
