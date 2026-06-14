"""Hybrid Qdrant search Lambda for codex_project."""

from __future__ import annotations

import json
import logging
import math
import os
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

import boto3
from huggingface_hub import InferenceClient
from qdrant_client import QdrantClient, models

from common import decimal_to_native, error_response, options_response, response


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
    if not raw_words:
        return True
    return len(raw_words) > 3


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


def _hf_timeout_seconds() -> float:
    try:
        return max(3.0, min(float(os.environ.get("HF_TIMEOUT_SECONDS", "25")), 30.0))
    except ValueError:
        return 25.0


def _hf_vector_dimension() -> int:
    try:
        return int(os.environ.get("HF_VECTOR_DIMENSION", "1024"))
    except ValueError:
        return 1024


class HuggingFaceEmbedder:
    """Generate dense embeddings through the official Hugging Face InferenceClient."""

    def __init__(
        self,
        *,
        api_key: str,
        model_id: str = "BAAI/bge-m3",
        vector_dimension: int = 1024,
        timeout_seconds: float = 25.0,
    ) -> None:
        self.client = InferenceClient(token=api_key, timeout=timeout_seconds)
        self.model_id = model_id
        self.vector_dimension = vector_dimension

    def generate_embedding(self, text: str) -> list[float]:
        embedding = self.client.feature_extraction(
            text=text,
            model=self.model_id,
        )
        result = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
        if isinstance(result, list) and result and isinstance(result[0], list):
            result = result[0]
        vector = [float(value) for value in result]
        if len(vector) != self.vector_dimension:
            raise ValueError(f"Expected {self.vector_dimension}-d vector, got {len(vector)}-d")
        return vector


def _dense_embedding(query: str) -> list[float]:
    hf_api_key = os.environ.get("HF_API_KEY")
    if not hf_api_key:
        raise RuntimeError("HF_API_KEY is required for dense query embeddings.")

    model_name = os.environ.get("HF_EMBEDDING_MODEL", "BAAI/bge-m3")
    embedder = HuggingFaceEmbedder(
        api_key=hf_api_key,
        model_id=model_name,
        vector_dimension=_hf_vector_dimension(),
        timeout_seconds=_hf_timeout_seconds(),
    )
    vector = embedder.generate_embedding(query)
    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [value / norm for value in vector]
    return vector


def _embedding_error_payload(error: Exception) -> dict[str, Any]:
    message = str(error)
    lowered = message.lower()

    if "hf_api_key is required" in lowered:
        return {
            "error": "Dense query embedding is not configured.",
            "code": "missing_hf_api_key",
            "hint": "Set HF_API_KEY in .env, then redeploy with make refresh.",
        }

    if "hugging face embedding request failed" in lowered:
        return {
            "error": "Dense query embedding provider failed.",
            "code": "hf_embedding_request_failed",
            "hint": "Check HF_API_KEY, HF_EMBEDDING_MODEL, Hugging Face availability, and Lambda CloudWatch logs.",
            "detail": message[:500],
        }

    return {
        "error": "Dense query embedding failed.",
        "code": "dense_embedding_failed",
        "hint": "Check HF_API_KEY, HF_EMBEDDING_MODEL, and Lambda CloudWatch logs.",
        "detail": message[:500],
    }


def _point_to_hit(point: Any) -> dict[str, Any]:
    return {
        "id": str(point.id),
        "score": float(point.score or 0.0),
        "payload": point.payload or {},
    }


def _query_text_from_payload(payload: dict[str, Any]) -> str:
    for key in ("query", "text", "question", "prompt"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def _dedupe_queries(queries: list[str], original_query: str, limit: int = 5) -> list[str]:
    original_normalized = original_query.strip().lower()
    seen: set[str] = set()
    output: list[str] = []
    for query in queries:
        cleaned = str(query or "").strip()
        normalized = cleaned.lower()
        if not cleaned or normalized == original_normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(cleaned)
        if len(output) >= limit:
            break
    return output


def _random_unit_vector(size: int) -> list[float]:
    values = [random.gauss(0, 1) for _ in range(size)]
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 0:
        return [0.0] * size
    return [value / norm for value in values]


def _related_queries_from_qdrant(
    client: QdrantClient,
    *,
    query_vector: list[float],
    original_query: str,
) -> list[str]:
    collection_name = os.environ.get("QUERY_COLLECTION_NAME", "codex_project-queries")
    if not collection_name:
        return []

    try:
        nearest = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using="dense",
            limit=20,
        ).points
    except Exception:
        logger.exception("Failed to query related-query collection %s", collection_name)
        return []

    nearest_queries = [_query_text_from_payload(point.payload or {}) for point in nearest]
    direct = nearest_queries[:3]
    tangential_pool = nearest_queries[3:20]
    tangential = [random.choice(tangential_pool)] if tangential_pool else []

    wildcard: list[str] = []
    try:
        wildcard_points = client.query_points(
            collection_name=collection_name,
            query=_random_unit_vector(len(query_vector)),
            using="dense",
            limit=1,
        ).points
        wildcard = [_query_text_from_payload(point.payload or {}) for point in wildcard_points]
    except Exception:
        logger.exception("Failed to query wildcard related query from %s", collection_name)

    return _dedupe_queries(direct + tangential + wildcard, original_query)


def _video_ids_from_hits(hits: list[dict[str, Any]]) -> list[str]:
    video_ids: list[str] = []
    for hit in hits:
        payload = hit.get("payload") or {}
        video_id = payload.get("video_id")
        if video_id and video_id not in video_ids:
            video_ids.append(str(video_id))
    return video_ids


def _load_video_metadata(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name or not video_ids:
        return {}

    table = boto3.resource("dynamodb").Table(table_name)
    lookup: dict[str, dict[str, Any]] = {}
    for video_id in video_ids[:25]:
        try:
            item = table.get_item(Key={"video_id": video_id}).get("Item")
        except Exception:
            logger.exception("Failed to load metadata for video_id=%s", video_id)
            continue
        if item:
            lookup[video_id] = decimal_to_native(item)
    return lookup


def _enrich_hits(hits: list[dict[str, Any]], metadata_lookup: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for hit in hits:
        payload = dict(hit.get("payload") or {})
        video_id = str(payload.get("video_id") or "")
        metadata = metadata_lookup.get(video_id) or {}
        for key in ("title", "summary", "topics", "target_audience", "difficulty_level", "queries"):
            if metadata.get(key) is not None and payload.get(key) in (None, "", []):
                payload[key] = metadata[key]
        enriched.append({**hit, "payload": payload})
    return enriched


def _fallback_related_queries(raw_query: str) -> list[str]:
    tokens = _tokenize(raw_query)
    if "discipline" in tokens or "consistent" in tokens:
        return [
            "How do I stay consistent with workouts?",
            "How can I build discipline when motivation drops?",
            "What routine helps beginners keep training?",
        ]
    if "fat" in tokens or "weight" in tokens:
        return [
            "What helps beginners lose fat safely?",
            "How should I combine diet and training?",
            "How do I avoid quitting during fat loss?",
        ]
    return [
        "How can I build mental toughness?",
        "How do I stop quitting when training gets hard?",
        "How should I recover after a bad week?",
    ]


def _related_queries_from_metadata(raw_query: str, metadata_lookup: dict[str, dict[str, Any]]) -> list[str]:
    raw_normalized = raw_query.strip().lower()
    query_tokens = set(_tokenize(raw_query))
    suggestions: list[str] = []

    for metadata in metadata_lookup.values():
        for query in metadata.get("queries") or []:
            query_text = str(query or "").strip()
            if not query_text or query_text.lower() == raw_normalized or query_text in suggestions:
                continue
            suggestion_tokens = set(_tokenize(query_text))
            if not query_tokens or query_tokens.intersection(suggestion_tokens):
                suggestions.append(query_text)
            if len(suggestions) >= 6:
                return suggestions

    for query in _fallback_related_queries(raw_query):
        if query.lower() != raw_normalized and query not in suggestions:
            suggestions.append(query)
        if len(suggestions) >= 6:
            break
    return suggestions


def _related_queries(
    client: QdrantClient,
    *,
    query_vector: list[float],
    raw_query: str,
    metadata_lookup: dict[str, dict[str, Any]],
) -> list[str]:
    qdrant_queries = _related_queries_from_qdrant(client, query_vector=query_vector, original_query=raw_query)
    if qdrant_queries:
        return qdrant_queries
    return _related_queries_from_metadata(raw_query, metadata_lookup)


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if event.get("httpMethod") == "OPTIONS":
        return options_response()

    try:
        query = _query_param(event, "q") or _query_param(event, "query")
        if not query:
            return error_response("Missing required query parameter: q", 400)

        limit = min(max(int(_query_param(event, "limit", "10")), 1), 50)
        search_type = _query_param(event, "type", "combined")
        qdrant_url = os.environ["QDRANT_URL"]
        qdrant_api_key = os.environ.get("QDRANT_API_KEY")
        collection_name = os.environ.get("COLLECTION_NAME", "codex_project-videos")
        processed_query = query

        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=20)
        try:
            dense_vector = _dense_embedding(processed_query)
        except Exception as exc:
            logger.exception("Dense query embedding failed")
            return response(503, _embedding_error_payload(exc))

        sparse_vector = None if _should_skip_sparse(processed_query) else _build_sparse_query(processed_query)

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
        metadata_lookup = _load_video_metadata(_video_ids_from_hits(hits))
        hits = _enrich_hits(hits, metadata_lookup)
        return response(
            200,
            {
                "query": query,
                "processed_query": processed_query,
                "type": search_type,
                "mode": mode,
                "threshold": threshold,
                "count": len(hits),
                "results": hits,
                "related_queries": _related_queries(
                    client,
                    query_vector=dense_vector,
                    raw_query=query,
                    metadata_lookup=metadata_lookup,
                ),
            },
        )
    except Exception as exc:
        logger.exception("Search failed")
        return error_response(str(exc))
