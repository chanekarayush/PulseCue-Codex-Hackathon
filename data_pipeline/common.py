"""Shared utilities for the Ditto data pipeline."""

from __future__ import annotations

import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable, TypeVar


LOGGER_NAME = "ditto_pipeline"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured pipeline logger."""

    logger = logging.getLogger(name or LOGGER_NAME)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    return logger


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def ensure_parent(path: str | Path) -> Path:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def save_json_atomic(path: str | Path, payload: Any) -> Path:
    """Write JSON via a temp file so interrupted runs do not corrupt outputs."""

    output_path = ensure_parent(path)
    tmp_path = output_path.with_name(f".{output_path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")
    tmp_path.replace(output_path)
    return output_path


def skip_if_exists(path: str | Path, logger: logging.Logger | None = None) -> bool:
    output_path = Path(path)
    if output_path.exists():
        (logger or get_logger()).info("Skipping existing output: %s", output_path)
        return True
    return False


def sanitize_stem(value: str) -> str:
    """Create a stable filesystem-safe stem while preserving readability."""

    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "untitled"


def iter_json_files(directory: str | Path) -> Iterable[Path]:
    yield from sorted(Path(directory).glob("*.json"))


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extract the first complete JSON object from noisy LLM text.

    This uses brace counting and string/escape tracking so braces inside JSON
    strings do not prematurely end the scan.
    """

    if not raw_text or not raw_text.strip():
        raise ValueError("LLM response is empty; cannot parse JSON.")

    start = raw_text.find("{")
    if start < 0:
        raise ValueError("No JSON object opening brace found in LLM response.")

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(raw_text)):
        char = raw_text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                json_text = raw_text[start : index + 1]
                return json.loads(json_text)

    raise ValueError("No complete JSON object found in LLM response.")


def is_rate_limit_error(error: BaseException) -> bool:
    """Best-effort rate-limit/quota detection across OpenAI, Google, HTTP libs."""

    status_code = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status_code == 429:
        return True

    response = getattr(error, "response", None)
    response_status = getattr(response, "status_code", None)
    if response_status == 429:
        return True

    message = str(error).lower()
    needles = (
        "429",
        "too many requests",
        "rate limit",
        "ratelimit",
        "quota",
        "resource exhausted",
    )
    return any(needle in message for needle in needles)


T = TypeVar("T")


def call_with_backoff(
    operation: Callable[[], T],
    *,
    logger: logging.Logger | None = None,
    max_attempts: int = 6,
    base_delay_seconds: float = 2.0,
    max_delay_seconds: float = 90.0,
) -> T:
    """Run an operation with exponential backoff for 429/quota failures."""

    log = logger or get_logger()
    attempt = 0
    while True:
        attempt += 1
        try:
            return operation()
        except Exception as exc:
            if not is_rate_limit_error(exc) or attempt >= max_attempts:
                raise
            delay = min(max_delay_seconds, base_delay_seconds * (2 ** (attempt - 1)))
            jitter = random.uniform(0.0, min(1.0, delay * 0.1))
            sleep_for = delay + jitter
            log.warning(
                "Rate limit/quota error on attempt %s/%s; retrying in %.1fs: %s",
                attempt,
                max_attempts,
                sleep_for,
                exc,
            )
            time.sleep(sleep_for)

