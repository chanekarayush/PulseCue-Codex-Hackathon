# Colab Pipeline

Use `codex_project.ipynb` as the single Colab entrypoint for extraction, enrichment,
embedding, and Qdrant upload. It stores persistent data in Google Drive under
`codex_project/`.

This folder is also the place for additional notebooks that generate BGE-M3
embeddings from:

- `data_pipeline/videos/processed_chunks/*_chunks.json`
- `data_pipeline/books/processed_books_chunks/*_chunks.json`

The generated vectors can be uploaded to Qdrant with each chunk payload.
