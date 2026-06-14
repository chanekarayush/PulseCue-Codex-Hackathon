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
तुम्ही Ditto या आध्यात्मिक शोध यंत्रासाठी अत्यंत अचूक metadata extractor आहात.
तुम्हाला पूर्ण YouTube transcript दिला जाईल. फक्त वैध JSON object परत करा; markdown,
स्पष्टीकरण, code fence किंवा अतिरिक्त मजकूर लिहू नका.

JSON schema:
{
  "title_suggestion": "string",
  "summary": "string",
  "topics": ["string"],
  "questions": ["string"],
  "actionable_practices": [
    {"practice": "string", "why_it_matters": "string", "how_to_do_it": "string"}
  ],
  "quoted_verses": [
    {"verse": "string", "source": "string|null", "meaning": "string"}
  ],
  "stories": [
    {
      "title": "string",
      "summary": "string",
      "characters": ["string"],
      "spiritual_lesson": "string",
      "exact_start_text": "segment च्या transcript मधील पहिले 7-10 शब्द जसेच्या तसे",
      "exact_end_text": "segment च्या transcript मधील शेवटचे 7-10 शब्द जसेच्या तसे"
    }
  ],
  "musical_segments": [
    {
      "title": "string",
      "segment_type": "bhajan|kirtan|chant|music|other",
      "summary": "string",
      "exact_start_text": "segment च्या transcript मधील पहिले 7-10 शब्द जसेच्या तसे",
      "exact_end_text": "segment च्या transcript मधील शेवटचे 7-10 शब्द जसेच्या तसे"
    }
  ]
}

Critical rules:
1. exact_start_text आणि exact_end_text transcript मधून verbatim copy करा.
2. timestamps तयार करू नका; ते system code resolve करेल.
3. खात्री नसल्यास रिकामी list वापरा.
4. JSON keys वर दिलेल्या schema प्रमाणेच ठेवा.
""".strip()


def _resolve_timestamps(
    metadata: dict[str, Any],
    full_text: str,
    char_to_time_map: list[CharTimeSpan],
) -> dict[str, Any]:
    """Resolve story/music exact text anchors to interpolated transcript times."""

    resolved = dict(metadata)
    for key in ("stories", "musical_segments", "music_segments"):
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
