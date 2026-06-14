"""LangChain text splitting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 150


@dataclass(frozen=True)
class SplitChunk:
    text: str
    start_index: int
    end_index: int


def split_text_with_start_indices(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[SplitChunk]:
    """Split text and preserve absolute start indices via LangChain."""

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
        separators=["\n\n", "\n", "। ", ". ", "? ", "! ", "; ", ", ", " ", ""],
    )
    documents = splitter.create_documents([text])
    chunks: list[SplitChunk] = []
    cursor = 0
    for document in documents:
        chunk_text = document.page_content
        start_index = document.metadata.get("start_index")
        if start_index is None:
            found_at = text.find(chunk_text, cursor)
            start_index = found_at if found_at >= 0 else cursor
        cursor = int(start_index) + len(chunk_text)
        chunks.append(
            SplitChunk(
                text=chunk_text,
                start_index=int(start_index),
                end_index=int(start_index) + len(chunk_text),
            )
        )
    return chunks


def non_empty_texts(items: Iterable[str]) -> list[str]:
    return [item.strip() for item in items if item and item.strip()]
