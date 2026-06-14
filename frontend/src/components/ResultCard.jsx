import { ChevronDown, ChevronUp, Play, Plus, Share2 } from "lucide-react";
import { useMemo, useState } from "react";
import { usePlayer } from "../context/PlayerContext.jsx";

function formatTimestamp(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds || 0)));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const secs = value % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function shareUrl(result) {
  const start = Math.floor(Number(result.start_time || 0));
  const url = result.youtube_url
    ? `${result.youtube_url}${result.youtube_url.includes("?") ? "&" : "?"}t=${start}s`
    : "";
  return `https://wa.me/?text=${encodeURIComponent(`${result.title}\n${url}`)}`;
}

export default function ResultCard({ result }) {
  const [expanded, setExpanded] = useState(false);
  const { playVideo, queueVideo } = usePlayer();
  const longText = (result.text || "").length > 420;
  const timestamp = useMemo(() => formatTimestamp(result.start_time), [result.start_time]);

  return (
    <article className="resultCard videoResult">
      <button
        type="button"
        className="thumbButton"
        onClick={() => playVideo(result)}
        aria-label={`Play ${result.title} at ${timestamp}`}
      >
        {result.thumbnail_url ? (
          <img src={result.thumbnail_url} alt="" loading="lazy" />
        ) : (
          <span className="thumbnailFallback">{result.video_id || "Video"}</span>
        )}
        <span className="playOverlay">
          <Play size={21} fill="currentColor" />
        </span>
        <span className="timeBadge">{timestamp}</span>
      </button>

      <div className="resultContent">
        <div className="resultHeader">
          <span className="scoreBadge">Relevance {result.relevance}%</span>
          <div className="iconGroup">
            <button
              className="iconButton"
              type="button"
              onClick={() => queueVideo(result)}
              aria-label="Add to queue"
              title="Add to queue"
            >
              <Plus size={18} />
            </button>
            <a
              className="iconButton"
              href={shareUrl(result)}
              target="_blank"
              rel="noreferrer"
              aria-label="Share result"
              title="Share result"
            >
              <Share2 size={17} />
            </a>
          </div>
        </div>

        <h3>{result.title}</h3>
        <p className={`resultText ${expanded ? "expanded" : ""}`}>{result.text}</p>
        {longText && (
          <button className="viewMore" type="button" onClick={() => setExpanded((value) => !value)}>
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {expanded ? "View less" : "View more"}
          </button>
        )}
      </div>
    </article>
  );
}
