"""Hybrid Qdrant search Lambda for codex_project."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

from common import error_response, options_response, response


logger = logging.getLogger()
logger.setLevel(logging.INFO)

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+(?:'[a-zA-Z0-9]+)?", flags=re.UNICODE)
STOPWORDS_PATH = Path(__file__).with_name("english_stopwords.json")
VOCAB_PATH = Path(__file__).with_name("vocab_idf.json")


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


STOPWORDS = set(_load_json(STOPWORDS_PATH, []))
BM25 = _load_json(VOCAB_PATH, {"vocab": {}, "idf": {}, "avgdl": 1.0, "k1": 1.5, "b": 0.75})


def _query_param(event: dict[str, Any], name: str, default: str = "") -> str:
    params = event.get("queryStringParameters") or {}
    return str(params.get(name) or default).strip()


def _tokenize(text: str, *, remove_stopwords: bool = True) -> list[str]:
    tokens = [token.lower() for token in TOKEN_PATTERN.findall(text or "")]
    if remove_stopwords:
        tokens = [token for token in tokens if token not in STOPWORDS]
    return tokens


def _should_skip_sparse(raw_query: str) -> bool:
    raw_words = _tokenize(raw_query, remove_stopwords=False)
    content_words = _tokenize(raw_query, remove_stopwords=True)
    if not content_words:
        return True
    return len(raw_words) > 10 or len(content_words) > 6


def _build_sparse_query(query: str) -> models.SparseVector | None:
    vocab = BM25.get("vocab") or {}
    idf = BM25.get("idf") or {}
    if not vocab or not idf:
        return None

    tokens = _tokenize(query)
    counts = Counter(token for token in tokens if token in vocab)
    if not counts:
        return None

    avgdl = float(BM25.get("avgdl") or 1.0)
    k1 = float(BM25.get("k1") or 1.5)
    b = float(BM25.get("b") or 0.75)
    doc_len = len(tokens) or 1

    indices: list[int] = []
    values: list[float] = []
    for token, tf in counts.items():
        denominator = tf + k1 * (1 - b + b * (doc_len / max(avgdl, 1e-9)))
        score = float(idf.get(token, 0.0)) * ((tf * (k1 + 1)) / denominator)
        if score > 0:
            indices.append(int(vocab[token]))
            values.append(score)

    if not indices:
        return None
    return models.SparseVector(indices=indices, values=values)


def _extract_embedding(payload: Any) -> list[float]:
    if isinstance(payload, dict):
        if "embedding" in payload:
            return _extract_embedding(payload["embedding"])
        if "error" in payload:
            raise RuntimeError(f"Hugging Face embedding error: {payload['error']}")

    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Unexpected embedding response from Hugging Face.")

    if all(isinstance(value, (int, float)) for value in payload):
        return [float(value) for value in payload]

    if len(payload) == 1 and isinstance(payload[0], list):
        return _extract_embedding(payload[0])

    if all(isinstance(row, list) for row in payload):
        rows = [[float(value) for value in row] for row in payload if row]
        if not rows:
            raise RuntimeError("Embedding response had no numeric rows.")
        dimensions = len(rows[0])
        return [sum(row[index] for row in rows) / len(rows) for index in range(dimensions)]

    raise RuntimeError("Unexpected embedding response shape from Hugging Face.")


def _dense_embedding(query: str) -> list[float]:
    hf_api_key = os.environ.get("HF_API_KEY")
    if not hf_api_key:
        raise RuntimeError("HF_API_KEY is required for dense query embeddings.")

    model_name = os.environ.get("HF_EMBEDDING_MODEL", "BAAI/bge-m3")
    url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model_name}"
    request = urllib.request.Request(
        url,
        data=json.dumps({"inputs": query, "options": {"wait_for_model": True}}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {hf_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Hugging Face embedding request failed: {exc.code} {details}") from exc

    vector = _extract_embedding(payload)
    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [value / norm for value in vector]
    return vector


def _point_to_hit(point: Any) -> dict[str, Any]:
    return {
        "id": str(point.id),
        "score": float(point.score or 0.0),
        "payload": point.payload or {},
    }


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if event.get("httpMethod") == "OPTIONS":
        return options_response()

    try:
        query = _query_param(event, "q") or _query_param(event, "query")
        if not query:
            return error_response("Missing required query parameter: q", 400)

        limit = min(max(int(_query_param(event, "limit", "10")), 1), 50)
        qdrant_url = os.environ["QDRANT_URL"]
        qdrant_api_key = os.environ.get("QDRANT_API_KEY")
        collection_name = os.environ.get("COLLECTION_NAME", "codex_project-videos")

        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=20)
        dense_vector = _dense_embedding(query)
        sparse_vector = None if _should_skip_sparse(query) else _build_sparse_query(query)

        if sparse_vector:
            threshold = 0.01
            result = client.query_points(
                collection_name=collection_name,
                prefetch=[
                    models.Prefetch(query=dense_vector, using="dense", limit=limit * 3),
                    models.Prefetch(query=sparse_vector, using="sparse", limit=limit * 3),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit,
                score_threshold=threshold,
            )
            mode = "hybrid_rrf"
        else:
            threshold = 0.46
            result = client.query_points(
                collection_name=collection_name,
                query=dense_vector,
                using="dense",
                limit=limit,
                score_threshold=threshold,
            )
            mode = "dense"

        hits = [_point_to_hit(point) for point in result.points]
        hits = [hit for hit in hits if hit["score"] >= threshold]
        return response(
            200,
            {
                "query": query,
                "mode": mode,
                "threshold": threshold,
                "count": len(hits),
                "results": hits,
            },
        )
    except Exception as exc:
        logger.exception("Search failed")
        return error_response(str(exc))
