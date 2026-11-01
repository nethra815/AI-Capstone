// Each example was asked against the live pipeline (1 Nov 2026) and returned a verified answer.
export const EXAMPLES = [
  "What is the attendance condonation fee per course?",
  "hostel mein guest raat ko ruk sakta hai kya?",
  "How many books can a student borrow from the library?",
  "What is the minimum CGPA for placement registration?",
  "What is the maximum late payment penalty per instalment?",
  "How many days do I have to appeal a disciplinary decision?",
];

export function EmptyState({ onPick, disabled }: { onPick: (q: string) => void; disabled: boolean }) {
  return (
    <section className="animate-fade-in">
      <h1 className="font-serif text-title font-semibold text-ink">Ask about college rules</h1>
      <p className="mt-3 max-w-[60ch] font-serif text-answer text-ink-2">
        Answers are drawn only from SPIT's official documents, with a numbered source for every statement.
      </p>
      <h2 className="label mt-10 mb-3">Try one of these</h2>
      <ul className="divide-y divide-rule border-y border-rule">
        {EXAMPLES.map((q) => (
          <li key={q}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onPick(q)}
              className="w-full py-2.5 text-left text-[15px] text-accent transition-colors duration-150 hover:text-accent-hover hover:underline hover:underline-offset-4 disabled:text-ink-3 disabled:no-underline"
            >
              {q}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
