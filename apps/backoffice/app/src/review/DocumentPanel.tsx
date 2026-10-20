import { useCallback, useEffect, useRef, useState } from "react";
import RevealOriginalButton, { type RevealedOriginal } from "./RevealOriginalButton";
import PageMagnifier from "./PageMagnifier";
import StatusIcon from "./StatusIcon";
import { shortTitle, toneOf, type DocView, type Mark, type RequiredDoc } from "./evaluation";
import { visibleMarks, type Focus } from "./focus";

export default function DocumentPanel({
  caseId,
  docs,
  missing,
  focus,
  onSelect,
  onOpenMark,
  onPreviewError,
  running,
}: {
  caseId: string;
  running: boolean;
  docs: DocView[];
  missing: RequiredDoc[];
  focus: Focus | null;
  onSelect: (focus: Focus) => void;
  // A box on a page was clicked: select its rule.
  onOpenMark: (mark: Mark) => void;
  // A preview image failed to load, e.g. because its presigned link expired.
  onPreviewError: () => void;
}) {
  const doc = docs.find((d) => d.key === focus?.docKey) ?? docs[0];
  // The revealed original replaces the masked pages until hidden or another document is opened.
  const [original, setOriginal] = useState<(RevealedOriginal & { docKey: string }) | null>(null);
  const [magnifier, setMagnifier] = useState(true);
  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sectionRef = useRef<HTMLElement>(null);

  // A box is placed a third down the viewer; without one, the page top is.
  const scrollToFocus = useCallback(() => {
    const scroller = scrollRef.current;
    const page = focus && pageRefs.current[focus.page - 1];
    if (!scroller || !page) return;
    const bbox = focus.source?.page === focus.page ? focus.source.bbox : undefined;
    const top = page.offsetTop - scroller.offsetTop + (bbox ? bbox[1] * page.offsetHeight - scroller.clientHeight / 3 : 0);
    scroller.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }, [focus]);

  const hasPreview = !!doc?.pages.some(Boolean);

  useEffect(() => {
    if (!focus) return;
    // In the stacked (narrow) layout the panel can sit below the fold.
    const rect = sectionRef.current?.getBoundingClientRect();
    if (focus.nonce && rect && (rect.top > window.innerHeight || rect.bottom < 0)) {
      sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [focus]);

  // Pages arriving after the click (a document still loading) scroll once they render.
  useEffect(scrollToFocus, [scrollToFocus, hasPreview]);

  if (!doc) {
    return (
      <section className="cr-docs cr-docs--empty" aria-label="Documents">
        <p>{running ? "Documents appear here as the agent reads them." : "No documents referenced by this evaluation."}</p>
      </section>
    );
  }

  const activePage = focus?.docKey === doc.key ? focus.page : null;
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
              // Switching documents keeps the selected rule, so its boxes stay drawn.
              onClick={() => onSelect({ docKey: d.key, page: d.referencedPages[0] ?? 1, ruleId: focus?.ruleId, nonce: Date.now() })}
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
              className="kb-btn kb-btn--tertiary kb-btn--small cr-icon-btn"
              href={doc.pdf}
              target="_blank"
              rel="noreferrer"
              title="Open PDF (masked copy: signatures are blacked out)"
              aria-label="Open PDF"
            >
              <OpenIcon />
            </a>
          ) : (
            <button
              type="button"
              className="kb-btn kb-btn--tertiary kb-btn--small cr-icon-btn"
              disabled
              title="No masked PDF for this document"
              aria-label="Open PDF"
            >
              <OpenIcon />
            </button>
          )}
          {hasPreview && !shownOriginal && (
            <button
              type="button"
              className={`kb-btn kb-btn--tertiary kb-btn--small cr-icon-btn${magnifier ? " is-hover" : ""}`}
              aria-pressed={magnifier}
              aria-label="Magnifier"
              onClick={() => setMagnifier((on) => !on)}
              title={`Magnifier ${magnifier ? "on" : "off"}: enlarge the page under the mouse`}
            >
              <MagnifierIcon />
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
                <>
                  <img
                    src={src}
                    alt={`${doc.title}, page ${i + 1}`}
                    loading={i < 3 || activePage === i + 1 ? "eager" : "lazy"}
                    onError={onPreviewError}
                    // The page's real height is known only now; re-aim at the box, unless a later link refresh reloads it.
                    onLoad={activePage === i + 1 ? () => focus && Date.now() - focus.nonce < 5000 && scrollToFocus() : undefined}
                  />
                  {visibleMarks(doc.marks, i + 1, focus).map(({ mark: m, label }) => {
                    const [x0, y0, x1, y1] = m.source.bbox!;
                    const active = m.source.id === focus?.source?.id;
                    const tone = toneOf(m.source, m.status);
                    return (
                      <button
                        key={m.source.id}
                        type="button"
                        className={`cr-mark cr-mark--${tone} cr-mark--${m.source.anchor}${active ? " is-active" : ""}`}
                        style={{ left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` }}
                        title={label}
                        aria-label={label}
                        onClick={() => onOpenMark(m)}
                      />
                    );
                  })}
                  {magnifier && <PageMagnifier src={src} />}
                </>
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

function OpenIcon() {
  return (
    <svg className="kb-icon kb-icon--16" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M14 3h7v7h-2V6.4l-9.3 9.3-1.4-1.4L17.6 5H14V3ZM5 5h6v2H5v12h12v-6h2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" />
    </svg>
  );
}

function MagnifierIcon() {
  return (
    <svg className="kb-icon kb-icon--16" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10 3a7 7 0 0 1 5.6 11.2l5.1 5.1-1.4 1.4-5.1-5.1A7 7 0 1 1 10 3Zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10Zm-1 2h2v2h2v2h-2v2H9v-2H7V9h2V7Z" />
    </svg>
  );
}
