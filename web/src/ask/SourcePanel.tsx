import { useEffect, useMemo, useRef } from "react";
import { Check, CircleAlert, ExternalLink, X } from "lucide-react";
import { api, pdfUrl, type Citation, type Claim, type DocumentInfo } from "../api";
import { clauseLabels, formatDate } from "../lib/format";
import { useLoad } from "../lib/hooks";
import { Highlight, keyTerms } from "./highlight";

function Passage({ citation, terms }: { citation: Citation; terms: string[] }) {
  const { data, error } = useLoad(() => api.passage(citation.chunk_id));
  const text = (data?.text ?? (error ? citation.excerpt : "")).replace(/\s+/g, " ").trim();
  return (
    <figure className="mt-4">
      <figcaption className="label mb-1.5">{data || !error ? "Passage" : "Excerpt"}</figcaption>
      {text ? (
        <blockquote className="border-l-2 border-accent/40 pl-3 font-serif text-[15px] leading-relaxed text-ink">
          <Highlight text={text} terms={terms} />
        </blockquote>
      ) : (
        <p className="text-small text-ink-3">Loading passage…</p>
      )}
    </figure>
  );
}

function CitationBlock({ citation, terms, doc }: { citation: Citation; terms: string[]; doc?: DocumentInfo }) {
  const page = citation.pages[0];
  const meta: [string, React.ReactNode][] = [
    ["Document ID", <span className="font-mono text-mono">{citation.doc_id}</span>],
    ["Version", citation.version === "?" ? "Not stated" : citation.version],
    ["Section", citation.section],
    ["Clauses", <span className="font-mono text-mono">{clauseLabels(citation.clauses, citation.section).join(", ") || "—"}</span>],
    [citation.pages.length > 1 ? "Pages" : "Page", citation.pages.join(", ") || "—"],
    ["Published", formatDate(citation.published_on)],
    ["Effective from", formatDate(citation.effective_from)],
  ];
  return (
    <section className="py-5">
      <h3 className="font-serif text-[19px] leading-snug font-semibold text-ink">{doc?.display_title ?? citation.title}</h3>
      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-small">
        {meta.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-3">{k}</dt>
            <dd className="min-w-0 break-words text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <Passage citation={citation} terms={terms} />
      <a href={pdfUrl(citation.doc_id, page)} target="_blank" rel="noreferrer" className="link mt-4 inline-flex items-center gap-1.5 text-small">
        Open PDF{page ? ` at page ${page}` : ""} <ExternalLink size={14} aria-hidden />
      </a>
    </section>
  );
}

interface Props {
  number: number;
  claim: Claim;
  docsById: Map<string, DocumentInfo>;
  onClose: () => void;
}

export function SourcePanel({ number, claim, docsById, onClose }: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const terms = useMemo(() => keyTerms(claim.text), [claim.text]);

  useEffect(() => {
    headingRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <>
      {/* Backdrop only on small screens, where the panel is a bottom sheet. */}
      <div aria-hidden onClick={onClose} className="fixed inset-0 z-30 animate-fade-in bg-ink/20 lg:hidden" />
      <aside
        role="dialog"
        aria-labelledby="source-heading"
        className="fixed inset-x-0 bottom-0 z-40 flex max-h-[82vh] animate-slide-in-up flex-col rounded-t-md border-t border-rule-strong bg-paper-raised shadow-[0_-1px_0_rgba(0,0,0,0.02)] lg:inset-x-auto lg:top-0 lg:right-0 lg:max-h-none lg:w-[420px] lg:animate-slide-in-right lg:rounded-none lg:border-t-0 lg:border-l"
      >
        <header className="flex items-start justify-between gap-3 border-b border-rule px-5 pt-4 pb-3">
          <div>
            <h2 id="source-heading" ref={headingRef} tabIndex={-1} className="label outline-none">
              Source {number}
            </h2>
            <p className="mt-1 flex items-center gap-1.5 text-small">
              {claim.verified ? (
                <>
                  <Check size={16} aria-hidden className="text-accent" />
                  <span className="text-ink">Verified against the source</span>
                </>
              ) : (
                <>
                  <CircleAlert size={16} aria-hidden className="text-changed" />
                  <span className="text-ink">Not verified</span>
                </>
              )}
              <span className="text-ink-3">· support {claim.support_score.toFixed(2)}</span>
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close source panel" className="-mr-1 rounded-sm p-1 text-ink-3 hover:text-ink">
            <X size={16} aria-hidden />
          </button>
        </header>
        <div className="overflow-y-auto overscroll-contain px-5">
          <p className="border-b border-rule py-4 font-serif text-[15px] leading-relaxed text-ink-2 italic">“{claim.text}”</p>
          <div className="divide-y divide-rule">
            {claim.citations.map((c) => (
              <CitationBlock key={c.chunk_id} citation={c} terms={terms} doc={docsById.get(c.doc_id)} />
            ))}
          </div>
        </div>
      </aside>
    </>
  );
}
