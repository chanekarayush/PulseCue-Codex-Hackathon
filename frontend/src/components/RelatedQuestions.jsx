export default function RelatedQuestions({ questions = [], onSelect }) {
  const items = questions.filter(Boolean).slice(0, 8);
  if (!items.length) {
    return null;
  }

  return (
    <div className="relatedQuestions" aria-label="Related questions">
      {items.map((question) => (
        <button
          className="questionPill"
          type="button"
          key={question}
          onClick={() => onSelect(question)}
        >
          {question}
        </button>
      ))}
    </div>
  );
}
