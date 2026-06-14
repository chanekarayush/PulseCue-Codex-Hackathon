# DynamoDB Metadata Schema

The video metadata table stores one item per YouTube video.

Default table:

```text
codex_project-content
```

Partition key:

```text
video_id (String)
```

## Video Item

```json
{
  "video_id": "youtube_video_id",
  "source_type": "youtube_video",
  "title": "Video title or LLM title suggestion",
  "summary": "Short video summary",
  "target_audience": ["beginners", "busy professionals"],
  "difficulty_level": "beginner|intermediate|advanced|mixed|unknown",
  "topics": ["discipline", "fat loss", "running"],
  "queries": [
    "How do I build discipline for fitness?",
    "How can I run longer without quitting?"
  ],
  "experiences": [
    {
      "title": "Overcoming childhood adversity",
      "experience_type": "personal_experience",
      "summary": "Short factual summary",
      "lesson": "Practical lesson from the experience",
      "start_time_seconds": 70,
      "end_time_seconds": 109
    }
  ],
  "fitness_advice": [
    {
      "advice": "Use progressive overload instead of random hard workouts.",
      "for_whom": ["beginner", "intermediate"],
      "category": "training",
      "why_it_matters": "It creates measurable adaptation.",
      "how_to_apply": "Add reps, load, or time gradually each week.",
      "start_time_seconds": 740,
      "end_time_seconds": 780
    }
  ],
  "motivational_takeaways": [
    {
      "takeaway": "Discomfort is part of growth.",
      "context": "Speaker discusses pushing through hard training."
    }
  ],
  "generated_at": "2026-06-14T00:00:00+00:00",
  "transcript_char_count": 123456
}
```

## What Is Not Stored

The DynamoDB row intentionally does not store local/debug-only fields:

- `exact_start_text`
- `exact_end_text`
- `timestamp_resolution`
- `start_char`
- `end_char`
- `pk`
- `sk`
- full raw LLM response fields

Those can remain in local `enriched_metadata/*.json` files for debugging, but the
app-facing DynamoDB item stays small and predictable.

## Query Strategy

`queries` is only a list of search-intent questions. It does not include answers
or timestamps. Search results should come from Qdrant transcript chunks, while
the query list can power suggestions, autocomplete, or admin review.

