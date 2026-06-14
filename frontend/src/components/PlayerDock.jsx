import { ListVideo, Play, X } from "lucide-react";
import { usePlayer } from "../context/PlayerContext.jsx";

function embedUrl(video) {
  const start = Math.max(0, Math.floor(Number(video.start_time || 0)));
  return `https://www.youtube.com/embed/${video.video_id}?start=${start}&autoplay=1&rel=0`;
}

export default function PlayerDock() {
  const { activeVideo, closePlayer, queue, playVideo, removeFromQueue } = usePlayer();

  if (!activeVideo && queue.length === 0) {
    return null;
  }

  return (
    <div className="playerDock">
      {activeVideo && (
        <section className="miniPlayer" aria-label="Active video">
          <div className="miniPlayerTop">
            <span>{activeVideo.title}</span>
            <button type="button" className="iconButton" onClick={closePlayer} aria-label="Close player">
              <X size={17} />
            </button>
          </div>
          <iframe
            title={activeVideo.title}
            src={embedUrl(activeVideo)}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </section>
      )}

      {queue.length > 0 && (
        <section className="queueDock" aria-label="Video queue">
          <div className="queueTitle">
            <ListVideo size={16} />
            <span>{queue.length}</span>
          </div>
          {queue.slice(0, 3).map((item) => (
            <div className="queueItem" key={item.id}>
              <button type="button" onClick={() => playVideo(item)} aria-label={`Play ${item.title}`}>
                <Play size={14} fill="currentColor" />
              </button>
              <span>{item.title}</span>
              <button type="button" onClick={() => removeFromQueue(item.id)} aria-label="Remove from queue">
                <X size={14} />
              </button>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
