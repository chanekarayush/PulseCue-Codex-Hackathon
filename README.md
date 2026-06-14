# codex_project

Multimodal motivation and fitness search data pipeline for YouTube videos and PDF books.

The pipeline extracts raw source text, enriches it with an LLM, creates anchored
semantic chunks, generates BGE-M3 embeddings on Colab T4 GPU, and can upload
metadata/vectors to DynamoDB and Qdrant.

## What This Builds

- YouTube transcripts in `data_pipeline/videos/output/`
- Video LLM metadata in `data_pipeline/videos/enriched_metadata/`
- Zero-drift timestamped video chunks in `data_pipeline/videos/processed_chunks/`
- PDF page text in `data_pipeline/books/books_output/`
- Book LLM metadata in `data_pipeline/books/books_enriched_metadata/`
- Page-mapped book chunks in `data_pipeline/books/processed_books_chunks/`
- Optional BGE-M3 embedded chunks and Qdrant hybrid-search upload from Colab

## Recommended: Run In Google Colab

Use this notebook:

`data_pipeline/colab/codex_project.ipynb`

### Prerequisites

1. A Google account with Google Drive.
2. Google Colab with GPU runtime available.
3. Runtime set to **T4 GPU**:
   - Open the notebook in Colab.
   - Go to `Runtime -> Change runtime type`.
   - Select `T4 GPU`.
   - Save.
4. API keys added in Colab's Secrets panel.
5. For private GitHub repos, add a `GITHUB_TOKEN` secret with read access.
6. For book processing, upload PDFs to this Google Drive folder after Cell 1:
   - `/content/drive/MyDrive/codex_project/input_books`

### Colab Secrets To Set

Minimum for the default notebook flow, where `RUN_LLM_ENRICHMENT=True`,
`RUN_DYNAMO_UPLOAD=False`, and `RUN_QDRANT_UPLOAD=False`:

```text
OPENAI_API_KEY
```

Also add this if the GitHub repo is private:

```text
GITHUB_TOKEN
```

Only add these if you turn on `RUN_QDRANT_UPLOAD=True`:

```text
QDRANT_URL
QDRANT_API_KEY
```

Only add these if you turn on `RUN_DYNAMO_UPLOAD=True`:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_DEFAULT_REGION
DITTO_VIDEOS_TABLE
DITTO_BOOKS_TABLE
```

Optional overrides. You do not need these unless you want to change defaults:

```text
GITHUB_REPO_URL
GITHUB_BRANCH
DITTO_LLM_MODEL
DITTO_LLM_TEMPERATURE
DITTO_LLM_MAX_ATTEMPTS
DITTO_VIDEO_SEGMENTS_TABLE
VIDEO_QDRANT_COLLECTION
BOOK_QDRANT_COLLECTION
```

Default values used when optional overrides are missing:

```text
GITHUB_BRANCH=feat/data-processing
DITTO_LLM_MODEL=gpt-4o-mini
DITTO_LLM_TEMPERATURE=0
DITTO_LLM_MAX_ATTEMPTS=6
VIDEO_QDRANT_COLLECTION=codex_project-videos
BOOK_QDRANT_COLLECTION=codex_project-books
```

## Colab Run Steps

1. Open `data_pipeline/colab/codex_project.ipynb` in Google Colab.
2. Set runtime to **T4 GPU**.
3. Add the secrets listed above in Colab's Secrets sidebar.
4. Run Cell 1 to mount Google Drive and create:
   - `/content/drive/MyDrive/codex_project`
5. Run Cell 2 to clone only the `feat/data-processing` branch, install dependencies, and symlink Drive folders.
6. Run Cell 3 and configure:
   - `VIDEO_URLS`
   - `RUN_VIDEOS`
   - `RUN_BOOKS`
   - `RUN_LLM_ENRICHMENT`
   - `RUN_DYNAMO_UPLOAD`
   - `RUN_EMBEDDINGS`
   - `RUN_QDRANT_UPLOAD`
7. Run the CPU cells for extraction, enrichment, and chunking.
8. Run the GPU cells for BGE-M3 embeddings.
9. Turn `RUN_QDRANT_UPLOAD = True` only when you are ready to upload vectors.
10. Run the verification cell to check output counts.

By default, the notebook does not upload to Qdrant or DynamoDB until you enable
those flags.

## Local Run Commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Video pipeline:

```bash
python -m data_pipeline.videos.main "https://www.youtube.com/watch?v=VIDEO_ID"
python -m data_pipeline.videos.video_enricher
python -m data_pipeline.videos.transcript_processor
```

Book pipeline:

```bash
python -m data_pipeline.books.books_main
```

Put PDFs in:

```text
data_pipeline/books/input_books/
```

## Cloud Backend

The AWS SAM backend lives in `cloud-backend/`.

Deployment guide:

```text
cloud-backend/PUBLISH.md
```

## Idempotency

Every file-producing phase checks whether its output already exists and skips it.
This prevents duplicate LLM calls and makes reruns safe.

## Notes

- Video timestamp mapping is character-offset based and uses interpolation inside
  transcript fragments for zero-drift chunk, experience, advice, and solved-query timestamps.
- Book chunking maps character offsets back to source page numbers.
