import { BookOpen, ChevronDown, ChevronUp, Share2 } from "lucide-react";
import { useState } from "react";

function pageLabel(result) {
  if (result.page_start && result.page_end && result.page_start !== result.page_end) {
    return `Pages ${result.page_start}-${result.page_end}`;
  }
  if (result.page_start) {
    return `Page ${result.page_start}`;
  }
  return "Book";
}

export default function BookResultCard({ result }) {
  const [expanded, setExpanded] = useState(false);
  const longText = (result.text || "").length > 420;
  const shareHref = `https://wa.me/?text=${encodeURIComponent(`${result.title}\n${result.text || ""}`)}`;

  return (
    <article className="resultCard bookResult">
      <div className="bookCover" aria-hidden="true">
        {result.cover_url ? <img src={result.cover_url} alt="" loading="lazy" /> : <BookOpen size={34} />}
        <span className="pageBadge">{pageLabel(result)}</span>
      </div>

      <div className="resultContent">
        <div className="resultHeader">
          <span className="scoreBadge">Relevance {result.relevance}%</span>
          <a
            className="iconButton"
            href={shareHref}
            target="_blank"
            rel="noreferrer"
            aria-label="Share result"
            title="Share result"
          >
            <Share2 size={17} />
          </a>
        </div>
        <h3>{result.title}</h3>
        {result.author && <span className="mutedLine">{result.author}</span>}
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
