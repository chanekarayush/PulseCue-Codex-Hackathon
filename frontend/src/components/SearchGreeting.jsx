import { useEffect, useMemo, useState } from "react";
import RelatedQuestions from "./RelatedQuestions.jsx";

const SUGGESTIONS = [
  "How do I stay consistent with workouts?",
  "How can I build mental toughness?",
  "What helps beginners lose fat safely?",
  "How do I stop quitting when training gets hard?",
  "How should I recover after a bad week?",
];

export default function SearchGreeting({ onSearch }) {
  const lines = useMemo(
    () => ["Train the question.", "Find the exact moment that answers it."],
    [],
  );
  const [lineIndex, setLineIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);

  useEffect(() => {
    if (lineIndex >= lines.length) {
      return undefined;
    }
    const currentLine = lines[lineIndex];
    if (charIndex < currentLine.length) {
      const timer = window.setTimeout(() => setCharIndex((value) => value + 1), 28);
      return () => window.clearTimeout(timer);
    }
    const timer = window.setTimeout(() => {
      setLineIndex((value) => value + 1);
      setCharIndex(0);
    }, 420);
    return () => window.clearTimeout(timer);
  }, [charIndex, lineIndex, lines]);

  const visibleLines = lines.slice(0, lineIndex);
  if (lineIndex < lines.length) {
    visibleLines.push(lines[lineIndex].slice(0, charIndex));
  }

  return (
    <section className="greeting" aria-label="Search start">
      <div className="greetingText">
        {visibleLines.map((line, index) => (
          <span key={`${line}-${index}`}>{line}</span>
        ))}
        <span className="cursor" aria-hidden="true" />
      </div>
      <RelatedQuestions questions={SUGGESTIONS} onSelect={onSearch} />
    </section>
  );
}
