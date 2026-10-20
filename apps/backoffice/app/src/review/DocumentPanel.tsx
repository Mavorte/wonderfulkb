import { useEffect, useRef, useState } from "react";
import RevealOriginalButton, { type RevealedOriginal } from "./RevealOriginalButton";
import StatusIcon from "./StatusIcon";
import type { DocView, RequiredDoc } from "./evaluation";

export interface Focus {
  docKey: string;
  page: number;
  // Changes on every click so re-selecting the same page scrolls again.
  nonce: number;
}

function shortTitle(title: string) {
  return title.replace(/\.pdf$/i, "").replace(/^\d+_/, "").replace(/_/g, " ");
}

export default function DocumentPanel({
  caseId,
  docs,
  missing,
  focus,
  onSelect,
  onPreviewError,
  running,
}: {
  caseId: string;
  running: boolean;
  docs: DocView[];
  missing: RequiredDoc[];
  focus: Focus | null;
  onSelect: (focus: Focus) => void;
  // A preview image failed to load, e.g. because its presigned link expired.
  onPreviewError: () => void;
}) {
  const doc = docs.find((d) => d.key === focus?.docKey) ?? docs[0];
  // The revealed original replaces the masked pages until hidden or another document is opened.
  const [original, setOriginal] = useState<(RevealedOriginal & { docKey: string }) | null>(null);
  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (!focus) return;
    // In the stacked (narrow) layout the panel can sit below the fold.
    const rect = sectionRef.current?.getBoundingClientRect();
    if (focus.nonce && rect && (rect.top > window.innerHeight || rect.bottom < 0)) {
      sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    const scroller = scrollRef.current;
    const page = pageRefs.current[focus.page - 1];
    if (scroller && page) scroller.scrollTo({ top: page.offsetTop - scroller.offsetTop, behavior: "smooth" });
  }, [focus]);

  if (!doc) {
    return (
      <section className="cr-docs cr-docs--empty" aria-label="Documents">
        <p>{running ? "Documents appear here as the agent reads them." : "No documents referenced by this evaluation."}</p>
      </section>
    );
  }

  const activePage = focus?.docKey === doc.key ? focus.page : null;
  const hasPreview = doc.pages.some(Boolean);
  const shownOriginal = original?.docKey === doc.key ? original : null;

  return (
    <section className="cr-docs" aria-label="Documents" ref={sectionRef}>
      <div className="cr-docs__strip" role="tablist" aria-label="Case documents">
        {docs.map((d) => {
          const cover = d.pages.find(Boolean);
          return (
            <button
              key={d.key}
              type="button"
              role="tab"
              aria-selected={d.key === doc.key}
              className="cr-thumb"
              onClick={() => onSelect({ docKey: d.key, page: d.referencedPages[0] ?? 1, nonce: Date.now() })}
              title={d.title}
            >
              <span className={`cr-thumb__img${cover ? "" : " is-unavailable"}`}>
                {cover ? (
                  <img src={cover} alt="" loading="lazy" onError={onPreviewError} />
                ) : d.loading ? (
                  <span className="cr-spinner" aria-hidden="true" />
                ) : (
                  <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm4 18H6V4h7v5h5v11Z" />
                  </svg>
                )}
                {d.status && (
                  <span className="cr-thumb__badge">
                    <StatusIcon status={d.status} size={16} />
                  </span>
                )}
              </span>
              <span className="cr-thumb__title">{shortTitle(d.title)}</span>
              <span className="cr-thumb__meta">{cover ? `${d.pages.length} p.` : d.loading ? "Loading…" : "No preview"}</span>
            </button>
          );
        })}
        {missing.map((m) => (
          <div key={m.description} className="cr-thumb cr-thumb--missing" title={m.description}>
            <span className="cr-thumb__img">
              <StatusIcon status="fail" />
              <span>Missing</span>
            </span>
            <span className="cr-thumb__title">{m.description}</span>
          </div>
        ))}
      </div>

      <header className="cr-docs__head">
        <div>
          <h2 className="cr-docs__title">{shortTitle(doc.title)}</h2>
          <p className="cr-docs__sub">
            {doc.title}
            {doc.referencedPages.length > 0 && ` · cited p. ${doc.referencedPages.join(", ")}`}
          </p>
        </div>
        <div className="cr-docs__actions">
          {doc.pdf ? (
            <a
              className="kb-btn kb-btn--tertiary kb-btn--small"
              href={doc.pdf}
              target="_blank"
              rel="noreferrer"
              title="Masked copy: signatures are blacked out"
            >
              Open PDF
            </a>
          ) : (
            <button type="button" className="kb-btn kb-btn--tertiary kb-btn--small" disabled title="No masked PDF for this document">
              Open PDF
            </button>
          )}
          <RevealOriginalButton
            key={doc.key}
            caseId={caseId}
            doc={doc}
            revealed={!!shownOriginal}
            onReveal={(revealed) => setOriginal({ ...revealed, docKey: doc.key })}
            onHide={() => setOriginal(null)}
          />
        </div>
      </header>

      {doc.fields.length > 0 && (
        <details className="cr-extracted" open={!hasPreview}>
          <summary>Extracted data</summary>
          <dl>
            {doc.fields.map((f) => (
              <div key={f.field} className={f.value ? undefined : "is-empty"}>
                <dt>{f.field.replace(/_/g, " ")}</dt>
                <dd>
                  {f.value ?? "not found"}
                  {f.page ? <span className="cr-muted"> · p. {f.page}</span> : null}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      )}

      {shownOriginal ? (
        <div className="cr-docs__pages cr-original">
          <p className="cr-original__note" role="status">
            Original with readable signatures. This reveal was audited.
          </p>
          {shownOriginal.contentType.startsWith("image/") ? (
            <img className="cr-original__image" src={shownOriginal.url} alt={`${shownOriginal.filename}, original`} />
          ) : (
            <iframe className="cr-original__frame" src={shownOriginal.url} title={`${shownOriginal.filename}, original`} />
          )}
        </div>
      ) : hasPreview ? (
        <div className="cr-docs__pages" ref={scrollRef}>
          {doc.pages.map((src, i) => (
            <div
              key={i}
              className={`cr-page${doc.referencedPages.includes(i + 1) ? " is-cited" : ""}${activePage === i + 1 ? " is-active" : ""}`}
              ref={(el) => {
                pageRefs.current[i] = el;
              }}
            >
              {src ? (
                <img src={src} alt={`${doc.title}, page ${i + 1}`} loading={i < 3 ? "eager" : "lazy"} onError={onPreviewError} />
              ) : (
                <div className="cr-page__missing">No preview for this page</div>
              )}
              <span className="cr-page__no">
                {doc.referencedPages.includes(i + 1) && "Cited · "}
                {i + 1} / {doc.pages.length}
              </span>
            </div>
          ))}
        </div>
      ) : doc.loading ? (
        <div className="cr-docs__pages cr-docs__unavailable" role="status">
          <div className="cr-loading">
            <span className="cr-spinner cr-spinner--32" aria-hidden="true" />
            <p>Loading pages…</p>
          </div>
        </div>
      ) : (
        <div className="cr-docs__pages cr-docs__unavailable">
          <div className="cr-unavailable">
            <svg className="kb-icon kb-icon--32" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm4 18H6V4h7v5h5v11Z" />
            </svg>
            <p>Page preview not available</p>
            <p className="cr-muted">{doc.unavailable ?? "The evaluation didn't record this document's id."}</p>
          </div>
        </div>
      )}
    </section>
  );
}
