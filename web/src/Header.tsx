import type { Route } from "./lib/hooks";

const TABS: { route: Route; label: string }[] = [
  { route: "ask", label: "Ask" },
  { route: "documents", label: "Documents" },
  { route: "research", label: "Research" },
];

export function Header({ route }: { route: Route }) {
  return (
    <header className="border-b border-rule bg-paper">
      <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-x-6 gap-y-1 px-4 pt-4 sm:px-6">
        <a href="#/ask" className="pb-3 no-underline">
          <span className="font-serif text-[19px] font-semibold tracking-[-0.01em] text-ink">SPIT Campus Assistant</span>
          <span className="ml-3 hidden text-small text-ink-3 sm:inline">Research prototype · synthetic data</span>
        </a>
        <nav aria-label="Main" className="-mb-px flex gap-5">
          {TABS.map((t) => {
            const active = t.route === route;
            return (
              <a
                key={t.route}
                href={`#/${t.route}`}
                aria-current={active ? "page" : undefined}
                className={`border-b-2 pb-3 text-ui font-medium transition-colors duration-150 ${
                  active ? "border-accent text-ink" : "border-transparent text-ink-3 hover:text-ink"
                }`}
              >
                {t.label}
              </a>
            );
          })}
        </nav>
        <p className="w-full pb-2 text-label text-ink-3 sm:hidden">Research prototype · synthetic data</p>
      </div>
    </header>
  );
}
