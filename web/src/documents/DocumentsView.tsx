import { ArrowRight, FileText } from "lucide-react";
import { api, pdfUrl, type DocStatus, type DocumentInfo } from "../api";
import { formatDate } from "../lib/format";
import { useLoad, type HealthState } from "../lib/hooks";
import { StatusLine } from "../lib/Status";

const STATUS: Record<DocStatus, { label: string; cls: string }> = {
  current: { label: "Current", cls: "bg-accent-tint text-accent" },
  superseded: { label: "Superseded", cls: "text-ink-3 border border-rule-strong" },
  circular: { label: "Circular", cls: "bg-changed-tint text-changed" },
  upcoming: { label: "Not yet effective", cls: "text-changed border border-changed/40" },
};

function StatusTag({ doc }: { doc: DocumentInfo }) {
  const s = STATUS[doc.status];
  return (
    <span className={`inline-block rounded-sm px-1.5 py-px text-label font-medium whitespace-nowrap ${s.cls}`}>
      {s.label}
      {doc.status === "upcoming" && doc.doc_type === "circular" ? " · circular" : ""}
    </span>
  );
}

/** Chains like Attendance Policy 2024-25 -> 2026-27 -> Revised Circular, from supersedes and amends links. */
function chainsFor(docs: DocumentInfo[]): DocumentInfo[][] {
  const byId = new Map(docs.map((d) => [d.id, d]));
  const chains: DocumentInfo[][] = [];
  for (const start of docs) {
    if (start.doc_type === "circular" || (start.supersedes && byId.has(start.supersedes))) continue;
    const chain = [start];
    let cur = start;
    while (cur.superseded_by && byId.has(cur.superseded_by)) {
      cur = byId.get(cur.superseded_by)!;
      chain.push(cur);
    }
    const circulars = docs.filter((d) => d.doc_type === "circular" && d.amends.includes(cur.id));
    chain.push(...circulars);
    if (chain.length > 1) chains.push(chain);
  }
  return chains;
}

function Chain({ chain }: { chain: DocumentInfo[] }) {
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small text-ink-2">
      {chain.map((d, i) => (
        <span key={d.id} className="flex items-center gap-2">
          {i > 0 && <ArrowRight size={14} aria-label={chain[i].doc_type === "circular" ? "amended by" : "replaced by"} className="text-ink-3" />}
          <span className={d.status === "superseded" ? "text-ink-3" : "text-ink"}>{d.display_title}</span>
        </span>
      ))}
    </p>
  );
}

function effective(d: DocumentInfo) {
  if (!d.effective_from) return "Any date";
  return d.effective_to ? `${formatDate(d.effective_from)} – ${formatDate(d.effective_to)}` : `From ${formatDate(d.effective_from)}`;
}

function DocRow({ doc, known }: { doc: DocumentInfo; known: Set<string> }) {
  const supersededElsewhere = doc.supersedes && !known.has(doc.supersedes);
  return (
    <tr className="border-t border-rule align-top">
      <td className="py-3 pr-4">
        <a href={pdfUrl(doc.id)} target="_blank" rel="noreferrer" className="group inline-flex items-start gap-2">
          <FileText size={16} aria-hidden className="mt-0.5 shrink-0 text-ink-3 group-hover:text-accent" />
          <span className="font-serif text-[16px] leading-snug text-ink group-hover:text-accent group-hover:underline group-hover:underline-offset-4">
            {doc.display_title}
          </span>
        </a>
        <div className="mt-0.5 pl-6 font-mono text-mono text-ink-3">{doc.id}</div>
        {supersededElsewhere && (
          <div className="pl-6 text-label text-ink-3">
            Replaces <span className="font-mono">{doc.supersedes}</span> (not in this collection)
          </div>
        )}
        <div className="mt-1 pl-6 text-small text-ink-2 sm:hidden">
          v{doc.version === "?" ? "—" : doc.version} · {effective(doc)}
        </div>
      </td>
      <td className="hidden py-3 pr-4 font-mono text-mono text-ink-2 sm:table-cell">{doc.version === "?" ? "—" : doc.version}</td>
      <td className="hidden py-3 pr-4 text-small whitespace-nowrap text-ink-2 sm:table-cell">{effective(doc)}</td>
      <td className="py-3 text-right sm:text-left">
        <StatusTag doc={doc} />
      </td>
    </tr>
  );
}

export function DocumentsView({ health }: { health: HealthState }) {
  const ready = health.status === "ready";
  const { data, error, reload } = useLoad(api.documents, ready);

  const topics: [string, DocumentInfo[]][] = [];
  for (const d of data ?? []) {
    const group = topics.find(([t]) => t === d.topic);
    if (group) group[1].push(d);
    else topics.push([d.topic, [d]]);
  }
  const known = new Set((data ?? []).map((d) => d.id));

  return (
    <div className="mx-auto max-w-5xl px-4 pt-10 pb-16 sm:px-6">
      <h1 className="font-serif text-title font-semibold">Documents</h1>
      <p className="mt-2 max-w-[65ch] text-ui text-ink-2">
        Every document the assistant reads, grouped by topic. Status is shown for today; older editions still govern
        dates before they were replaced. Select a title to open its PDF.
      </p>
      {!ready && (
        <div className="mt-6">
          <StatusLine health={health} />
        </div>
      )}
      {error && (
        <p role="alert" className="mt-6 text-ui text-changed">
          {error}{" "}
          <button type="button" className="link" onClick={reload}>
            Try again
          </button>
        </p>
      )}
      {data && (
        <p className="mt-4 text-small text-ink-3">
          {data.length} documents · {data.filter((d) => d.status === "current").length} current ·{" "}
          {data.filter((d) => d.status === "superseded").length} superseded · {data.filter((d) => d.doc_type === "circular").length} circulars
        </p>
      )}
      <div className="mt-8 space-y-12">
        {topics.map(([topic, docs]) => {
          const chains = chainsFor(docs);
          return (
            <section key={topic} aria-labelledby={`t-${topic}`} className="animate-fade-in">
              <h2 id={`t-${topic}`} className="font-serif text-subhead font-semibold">
                {topic}
              </h2>
              {chains.length > 0 && (
                <div className="mt-2 space-y-1">
                  {chains.map((c) => (
                    <Chain key={c[0].id} chain={c} />
                  ))}
                </div>
              )}
              <table className="mt-3 w-full table-fixed border-b border-rule text-left">
                <thead>
                  <tr>
                    <th scope="col" className="label pb-2 font-medium">Document</th>
                    <th scope="col" className="label hidden w-20 pb-2 font-medium sm:table-cell">Version</th>
                    <th scope="col" className="label hidden w-56 pb-2 font-medium sm:table-cell">Effective</th>
                    <th scope="col" className="label w-32 pb-2 text-right font-medium sm:w-44 sm:text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <DocRow key={d.id} doc={d} known={known} />
                  ))}
                </tbody>
              </table>
            </section>
          );
        })}
      </div>
    </div>
  );
}
