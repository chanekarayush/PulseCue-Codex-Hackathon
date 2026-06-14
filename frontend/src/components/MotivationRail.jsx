import { Clock3, Dumbbell, Library, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { getExperiences, getVideos } from "../utils/api.js";

function formatTime(seconds) {
  if (seconds === null || seconds === undefined) {
    return "";
  }
  const value = Math.max(0, Math.floor(Number(seconds || 0)));
  const minutes = Math.floor(value / 60);
  const secs = value % 60;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export default function MotivationRail({ onSearch }) {
  const [experiences, setExperiences] = useState([]);
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([getExperiences(), getVideos()])
      .then(([experienceResult, videoResult]) => {
        if (cancelled) {
          return;
        }
        if (experienceResult.status === "fulfilled") {
          setExperiences(experienceResult.value.slice(0, 4));
        }
        if (videoResult.status === "fulfilled") {
          setVideos(videoResult.value.slice(0, 3));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <aside className="motivationRail" aria-label="Motivation feed">
      <section className="railSection">
        <div className="railHeading">
          <Dumbbell size={18} />
          <h2>Experiences</h2>
        </div>
        {loading && (
          <div className="railLoading">
            <Loader2 size={18} className="spin" />
          </div>
        )}
        {!loading && experiences.length === 0 && <p className="railEmpty">No experience metadata yet.</p>}
        {experiences.map((item) => (
          <button
            className="experienceItem"
            type="button"
            key={item.experience_id || `${item.video_id}-${item.title}`}
            onClick={() => onSearch(item.lesson || item.title || item.summary)}
          >
            <span>{item.title || "Training experience"}</span>
            <small>
              <Clock3 size={13} />
              {formatTime(item.start_time_seconds)}
            </small>
          </button>
        ))}
      </section>

      <section className="railSection">
        <div className="railHeading">
          <Library size={18} />
          <h2>Library</h2>
        </div>
        {!loading && videos.length === 0 && <p className="railEmpty">No video metadata yet.</p>}
        {videos.map((video) => (
          <button
            className="libraryItem"
            type="button"
            key={video.video_id}
            onClick={() => onSearch((video.queries && video.queries[0]) || video.title)}
          >
            <span>{video.title || video.video_id}</span>
            <small>{(video.topics || []).slice(0, 2).join(" / ") || video.difficulty_level}</small>
          </button>
        ))}
      </section>
    </aside>
  );
}
