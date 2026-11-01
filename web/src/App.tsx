import { Header } from "./Header";
import { StatusLine } from "./lib/Status";
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
        <div className="mx-auto max-w-[720px] px-4 pt-10 sm:px-6">
          <h1 className="font-serif text-title font-semibold capitalize">{route}</h1>
          <div className="mt-4">
            <StatusLine health={health} />
          </div>
        </div>
      </main>
    </div>
  );
}
