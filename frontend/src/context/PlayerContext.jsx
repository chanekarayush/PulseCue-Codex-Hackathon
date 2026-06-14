import { createContext, useCallback, useContext, useMemo, useState } from "react";

const PlayerContext = createContext(null);

export function PlayerProvider({ children }) {
  const [activeVideo, setActiveVideo] = useState(null);
  const [queue, setQueue] = useState([]);

  const playVideo = useCallback((video) => {
    if (!video?.video_id) {
      return;
    }
    setActiveVideo(video);
  }, []);

  const closePlayer = useCallback(() => {
    setActiveVideo(null);
  }, []);

  const queueVideo = useCallback((video) => {
    if (!video?.video_id) {
      return;
    }
    setQueue((items) => {
      if (items.some((item) => item.id === video.id)) {
        return items;
      }
      return [...items, video];
    });
  }, []);

  const removeFromQueue = useCallback((id) => {
    setQueue((items) => items.filter((item) => item.id !== id));
  }, []);

  const value = useMemo(
    () => ({
      activeVideo,
      queue,
      playVideo,
      closePlayer,
      queueVideo,
      removeFromQueue,
    }),
    [activeVideo, closePlayer, playVideo, queue, queueVideo, removeFromQueue],
  );

  return <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>;
}

export function usePlayer() {
  const value = useContext(PlayerContext);
  if (!value) {
    throw new Error("usePlayer must be used inside PlayerProvider");
  }
  return value;
}
