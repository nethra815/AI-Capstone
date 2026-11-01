import { api, type EvalSummary, type ModeMetrics } from "../api";
import { formatDate, MODE_LABELS, pct, seconds } from "../lib/format";
import { useLoad, type HealthState } from "../lib/hooks";
import { BarChart } from "./BarChart";
import { CompareModes } from "./CompareModes";

type Metric = {
  key: keyof ModeMetrics;
  label: string;
  help: string;
  format: (m: ModeMetrics) => string;
  value?: (m: ModeMetrics) => number | null;
  higherIsBetter?: boolean;
};

const METRICS: Metric[] = [
  { key: "accuracy", label: "Answer accuracy", help: "Correct answers, and correct refusals for unanswerable questions", format: (m) => pct(m.accuracy, 1), value: (m) => m.accuracy, higherIsBetter: true },
  { key: "citation_verified", label: "Citations verified", help: "Claims whose cited passage supports them", format: (m) => pct(m.citation_verified, 1), value: (m) => m.citation_verified, higherIsBetter: true },
  { key: "abstention_recall", label: "Abstention recall", help: "Unanswerable questions it declined to answer", format: (m) => pct(m.abstention_recall, 1), value: (m) => m.abstention_recall, higherIsBetter: true },
  { key: "over_refusal", label: "Over-refusal", help: "Answerable questions it declined", format: (m) => pct(m.over_refusal, 1), value: (m) => m.over_refusal },
  { key: "abstention_rate", label: "Abstention rate", help: "All questions it declined", format: (m) => pct(m.abstention_rate, 1) },
  { key: "stale_errors", label: "Stale-rule errors", help: "Answers that gave an outdated value", format: (m) => String(m.stale_errors) },
  { key: "recall_at_5", label: "Retrieval recall@5", help: "Gold passage among the top five retrieved", format: (m) => pct(m.recall_at_5, 1), value: (m) => m.recall_at_5, higherIsBetter: true },
  { key: "avg_latency_ms", label: "Average latency", help: "Per question, after startup", format: (m) => seconds(m.avg_latency_ms) },
  { key: "n", label: "Questions", help: "Rows evaluated in this mode", format: (m) => String(m.n) },
];

function MetricsTable({ data }: { data: EvalSummary }) {
  return (
    <div className={`overflow-x-auto ${data.modes.length === 1 ? "max-w-2xl" : ""}`}>
      <table className="w-full min-w-[480px] border-y border-rule text-left">
        <thead>
          <tr className="border-b border-rule">
            <th scope="col" className="label py-2 pr-4 font-medium">Metric</th>
            {data.modes.map((m) => (
              <th key={m.mode} scope="col" className="label py-2 pr-4 text-right font-medium">
                {MODE_LABELS[m.mode] ?? m.mode}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRICS.map((metric) => (
            <tr key={metric.key} className="border-t border-rule first:border-t-0">
              <th scope="row" className="py-2.5 pr-4 font-normal">
                <div className="text-ui text-ink">{metric.label}</div>
                <div className="text-label text-ink-3">{metric.help}</div>
              </th>
              {data.modes.map((m) => (
                <td key={m.mode} className="py-2.5 pr-4 text-right font-mono text-mono tabular-nums text-ink">
                  {metric.format(m)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CategoryTable({ data }: { data: EvalSummary }) {
  const modes = data.modes.map((m) => m.mode);
  return (
    <div className={`overflow-x-auto ${modes.length === 1 ? "max-w-2xl" : ""}`}>
      <table className="w-full min-w-[360px] border-y border-rule text-left">
        <thead>
          <tr className="border-b border-rule">
            <th scope="col" className="label py-2 pr-4 font-medium">Question type</th>
            <th scope="col" className="label py-2 pr-4 text-right font-medium">Questions</th>
            {modes.map((m) => (
              <th key={m} scope="col" className="label py-2 pr-4 text-right font-medium">
                {MODE_LABELS[m] ?? m}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.categories.map((c) => (
            <tr key={c.category} className="border-t border-rule first:border-t-0">
              <th scope="row" className="py-2 pr-4 text-ui font-normal text-ink">
                {c.category[0].toUpperCase() + c.category.slice(1).replace(/_/g, " ")}
              </th>
              <td className="py-2 pr-4 text-right font-mono text-mono text-ink-2">{c.n}</td>
              {modes.map((m) => (
                <td key={m} className="py-2 pr-4 text-right font-mono text-mono tabular-nums text-ink">
                  {pct(c.accuracy[m])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ResearchView({ health }: { health: HealthState }) {
  const { data, error, reload } = useLoad(api.evalSummary);
  const single = data?.modes.length === 1;
  return (
    <div className="mx-auto max-w-5xl px-4 pt-10 pb-16 sm:px-6">
      <h1 className="font-serif text-title font-semibold">Research</h1>
      <p className="mt-2 max-w-[65ch] text-ui text-ink-2">
        How the four retrieval set-ups compare on the project benchmark, and a tool to compare them live on one question.
      </p>

      <section className="mt-10" aria-labelledby="bench">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="bench" className="font-serif text-subhead font-semibold">Benchmark results</h2>
          {data?.available && (
            <p className="text-small text-ink-3">
              {data.n_questions} questions · results file updated {formatDate(data.updated)}
            </p>
          )}
        </div>
        {error && (
          <p role="alert" className="mt-3 text-ui text-changed">
            {error}{" "}
            <button type="button" className="link" onClick={reload}>Try again</button>
          </p>
        )}
        {data && !data.available && (
          <p className="mt-3 text-ui text-ink-2">
            No results yet. Run <code className="font-mono text-mono">python eval/run_eval.py</code> to create{" "}
            <code className="font-mono text-mono">eval/results/per_question.csv</code>.
          </p>
        )}
        {data?.available && (
          <div className="mt-4 space-y-8">
            {single && (
              <p className="border-l-2 border-rule-strong pl-3 text-small text-ink-2">
                Only {MODE_LABELS[data.modes[0].mode] ?? data.modes[0].mode} ({data.modes[0].mode}) has been evaluated so
                far. Use Compare modes below to see how the others differ on a live question.
              </p>
            )}
            {!single && (
              <div className="grid gap-x-10 gap-y-8 sm:grid-cols-2">
                {METRICS.filter((m) => m.value).map((metric) => (
                  <BarChart
                    key={metric.key}
                    title={metric.label}
                    note={metric.higherIsBetter ? "Higher is better" : "Lower is better"}
                    rows={data.modes.map((m) => ({ label: MODE_LABELS[m.mode] ?? m.mode, value: metric.value!(m), display: metric.format(m) }))}
                  />
                ))}
              </div>
            )}
            <MetricsTable data={data} />
            <div>
              <h3 className="label mb-2">Accuracy by question type</h3>
              <CategoryTable data={data} />
            </div>
          </div>
        )}
      </section>

      <CompareModes health={health} />
    </div>
  );
}
