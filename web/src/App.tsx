import { Header } from "./Header";
import { AskView } from "./ask/AskView";
import { DocumentsView } from "./documents/DocumentsView";
import { ResearchView } from "./research/ResearchView";
import { useHealth, useRoute } from "./lib/hooks";

export default function App() {
  const route = useRoute();
  const health = useHealth();
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:bg-paper focus:px-2">
        Skip to content
      </a>
      <Header route={route} />
      <main id="main" className="flex-1">
        {/* Ask stays mounted so the session's conversation survives switching tabs. */}
        <div hidden={route !== "ask"}>
          <AskView health={health} />
        </div>
        {route === "documents" && <DocumentsView health={health} />}
        {route === "research" && <ResearchView health={health} />}
      </main>
    </div>
  );
}
