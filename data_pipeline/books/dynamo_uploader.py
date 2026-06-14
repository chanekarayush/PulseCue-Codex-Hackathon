"""Upload book metadata to DynamoDB."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from data_pipeline.common import get_logger, iter_json_files, load_json
from data_pipeline.dynamo import to_dynamo_value


LOGGER = get_logger(__name__)
BOOK_DIR = Path(__file__).resolve().parent
DEFAULT_METADATA_DIR = BOOK_DIR / "books_enriched_metadata"


def upload_metadata_file(metadata_path: str | Path, *, table_name: str) -> None:
    import boto3

    metadata = load_json(metadata_path)
    book_id = metadata.get("book_id") or Path(metadata_path).stem.replace("_meta", "")
    item = {
        **metadata,
        "book_id": book_id,
        "pk": f"BOOK#{book_id}",
        "sk": "METADATA",
    }
    table = boto3.resource("dynamodb").Table(table_name)
    table.put_item(Item=to_dynamo_value(item))
    LOGGER.info("Uploaded book metadata for %s to %s", book_id, table_name)


def upload_directory(
    *,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
    table_name: str | None = None,
) -> None:
    table_name = table_name or os.getenv("DITTO_BOOKS_TABLE")
    if not table_name:
        raise RuntimeError("Provide --table or set DITTO_BOOKS_TABLE.")

    for metadata_path in iter_json_files(metadata_dir):
        upload_metadata_file(metadata_path, table_name=table_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload book metadata to DynamoDB.")
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--file", type=Path, help="Upload one metadata JSON file.")
    parser.add_argument("--table", default=os.getenv("DITTO_BOOKS_TABLE"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.table:
        raise SystemExit("Provide --table or set DITTO_BOOKS_TABLE.")
    if args.file:
        upload_metadata_file(args.file, table_name=args.table)
    else:
        upload_directory(metadata_dir=args.metadata_dir, table_name=args.table)


if __name__ == "__main__":
    main()
