export const APP_NAME = "PulseCue";

function displayProjectName(value) {
  const clean = String(value || "").trim();
  return clean && clean !== "codex_project" ? clean : APP_NAME;
}

const FALLBACK_RELATED = [
  "How do I stay consistent with workouts?",
  "How can I build mental toughness?",
  "What helps beginners lose fat safely?",
  "How do I stop quitting when training gets hard?",
  "How should I recover after a bad week?",
];

let runtimeConfigPromise;

function trimTrailingSlash(value) {
  return String(value || "").replace(/\/+$/, "");
}

async function loadRuntimeConfig() {
  if (runtimeConfigPromise) {
    return runtimeConfigPromise;
  }

  runtimeConfigPromise = (async () => {
    const envApiUrl = trimTrailingSlash(import.meta.env.VITE_API_URL);
    if (envApiUrl) {
      return { apiUrl: envApiUrl, projectName: APP_NAME };
    }

    if (window.CODEX_PROJECT_CONFIG?.apiUrl) {
      return {
        projectName: displayProjectName(window.CODEX_PROJECT_CONFIG.projectName),
        apiUrl: trimTrailingSlash(window.CODEX_PROJECT_CONFIG.apiUrl),
      };
    }

    try {
      const response = await fetch("/config.json", { cache: "no-store" });
      if (response.ok) {
        const config = await response.json();
        return {
          projectName: displayProjectName(config.projectName),
          apiUrl: trimTrailingSlash(config.apiUrl),
        };
      }
    } catch {
      // Local development can use VITE_API_URL; deployed builds use /config.json.
    }

    return { projectName: APP_NAME, apiUrl: "" };
  })();

  return runtimeConfigPromise;
}

function scoreToPercent(score) {
  const value = Number(score || 0);
  if (value <= 1) {
    return Math.round(value * 100);
  }
  return Math.round(value);
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function youtubeThumbnail(videoId, fallback) {
  if (fallback) {
    return fallback;
  }
  if (!videoId) {
    return "";
  }
  return `https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`;
}

function normalizeVideoHit(hit, payload, score) {
  const videoId = payload.video_id || payload.videoId || payload.youtube_id || "";
  const startTime = numberOrNull(payload.start_time ?? payload.start_time_seconds);
  const endTime = numberOrNull(payload.end_time ?? payload.end_time_seconds);
  const youtubeUrl =
    payload.youtube_url || payload.url || (videoId ? `https://www.youtube.com/watch?v=${videoId}` : "");

  return {
    id: String(hit.id || payload.chunk_id || `${videoId}-${startTime || 0}`),
    type: "video",
    score,
    relevance: scoreToPercent(score),
    video_id: videoId,
    title: payload.title || payload.video_title || payload.source_title || "Training clip",
    text: payload.text || payload.chunk_text || payload.transcript || "",
    start_time: startTime,
    end_time: endTime,
    duration: numberOrNull(payload.duration),
    youtube_url: youtubeUrl,
    thumbnail_url: youtubeThumbnail(videoId, payload.thumbnail_url),
    topics: Array.isArray(payload.topics) ? payload.topics : [],
  };
}

function normalizeBookHit(hit, payload, score) {
  return {
    id: String(hit.id || payload.chunk_id || `${payload.book_id || "book"}-${payload.page_start || 0}`),
    type: "book",
    score,
    relevance: scoreToPercent(score),
    book_id: payload.book_id || "",
    title: payload.title || payload.book_title || payload.source_title || "Book passage",
    author: payload.author || "",
    text: payload.text || payload.chunk_text || "",
    page_start: numberOrNull(payload.page_start ?? payload.page),
    page_end: numberOrNull(payload.page_end),
    cover_url: payload.cover_url || payload.thumbnail_url || "",
    topics: Array.isArray(payload.topics) ? payload.topics : [],
  };
}

function normalizeSearchHit(hit) {
  const payload = hit?.payload || hit || {};
  const score = Number(hit?.score ?? payload.score ?? 0);
  const sourceType = payload.source_type || payload.content_type || payload.type;
  const isBook = sourceType === "pdf_book" || Boolean(payload.book_id);
  return isBook ? normalizeBookHit(hit, payload, score) : normalizeVideoHit(hit, payload, score);
}

function relatedFromQuery(query) {
  const clean = String(query || "").trim().replace(/[?.!]+$/, "");
  if (!clean) {
    return FALLBACK_RELATED;
  }
  return [
    `What should I do after ${clean.toLowerCase()}?`,
    `How do I apply this consistently?`,
    `What is the beginner version of this?`,
    `How do I avoid giving up?`,
  ];
}

async function request(path, params = {}) {
  const { apiUrl } = await loadRuntimeConfig();
  if (!apiUrl) {
    throw new Error("API URL is not configured. Set VITE_API_URL locally or deploy config.json with make upload_ui.");
  }

  const url = new URL(`${apiUrl}${path}`);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });

  const response = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const parts = [
      payload.error || `Request failed with ${response.status}`,
      payload.code ? `Code: ${payload.code}` : "",
      payload.hint || "",
      payload.detail ? `Detail: ${payload.detail}` : "",
    ].filter(Boolean);
    throw new Error(parts.join(" "));
  }
  return payload;
}

export async function search(query, options = {}) {
  const data = await request("/search", {
    q: query,
    type: options.type || "combined",
    limit: options.limit || 10,
  });
  const rawResults = data.results || data.hits || [];
  return {
    query,
    mode: data.mode || "search",
    results: rawResults.map(normalizeSearchHit).sort((a, b) => b.score - a.score),
    related_queries: Array.isArray(data.related_queries) && data.related_queries.length
      ? data.related_queries
      : relatedFromQuery(query),
  };
}

export async function getExperiences() {
  const data = await request("/experiences");
  return Array.isArray(data.experiences) ? data.experiences : [];
}

export async function getVideos() {
  const data = await request("/videos");
  return Array.isArray(data.videos) ? data.videos : [];
}

export async function getBooks() {
  const data = await request("/books");
  return Array.isArray(data.books) ? data.books : [];
}

export async function getConfig() {
  return loadRuntimeConfig();
}
