import { useCallback, useEffect, useState } from "react";
import PlayerDock from "./components/PlayerDock.jsx";
import SearchPage from "./components/SearchPage.jsx";
import { PlayerProvider } from "./context/PlayerContext.jsx";
import { getConfig, search } from "./utils/api.js";

function makeSession(query) {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    query,
    results: [],
    loading: true,
    selectedFilter: "combined",
    related_queries: [],
    error: "",
  };
}

function navigateToSearch() {
  if (!["/search", "/motivation", "/"].includes(window.location.pathname)) {
    window.history.pushState({}, "", "/search");
    return;
  }
  if (window.location.pathname === "/") {
    window.history.pushState({}, "", "/search");
  }
}

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [config, setConfig] = useState({ projectName: "codex_project", apiUrl: "" });

  useEffect(() => {
    getConfig().then(setConfig).catch(() => undefined);
  }, []);

  const handleSearch = useCallback(async (query) => {
    const cleanQuery = String(query || "").trim();
    if (!cleanQuery) {
      return;
    }

    navigateToSearch();
    const session = makeSession(cleanQuery);
    setSessions((items) => [...items, session]);

    try {
      const payload = await search(cleanQuery);
      setSessions((items) =>
        items.map((item) =>
          item.id === session.id
            ? {
                ...item,
                loading: false,
                results: payload.results,
                related_queries: payload.related_queries,
              }
            : item,
        ),
      );
    } catch (error) {
      setSessions((items) =>
        items.map((item) =>
          item.id === session.id
            ? {
                ...item,
                loading: false,
                error: error.message || "Search failed.",
              }
            : item,
        ),
      );
    }
  }, []);

  const handleFilterChange = useCallback((sessionId, selectedFilter) => {
    setSessions((items) =>
      items.map((item) => (item.id === sessionId ? { ...item, selectedFilter } : item)),
    );
  }, []);

  return (
    <PlayerProvider>
      <div className="appShell" data-api-configured={Boolean(config.apiUrl)}>
        <SearchPage
          sessions={sessions}
          onSearch={handleSearch}
          onFilterChange={handleFilterChange}
        />
        <PlayerDock />
      </div>
    </PlayerProvider>
  );
}
