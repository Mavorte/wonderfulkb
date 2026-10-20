import { useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import type { DocView } from "./evaluation";

/**
 * The readable original as the document-original Function returns it; the links expire after 60 s.
 * `pages[i]` renders page i + 1 at the size of the masked page, so the same boxes fit; null while not rendered.
 */
export type RevealedOriginal = { url: string; filename: string; contentType: string; pages: (string | null)[] };

type OriginalResponse = (RevealedOriginal & { expiresIn: number; error?: undefined }) | { error: string };

const errorText: Record<string, string> = {
  not_found: "The documents API has no original for this document.",
  unauthenticated: "Sign in to reveal the original.",
};

type Props = {
  caseId: string;
  doc: DocView;
  revealed: boolean;
  onReveal: (original: RevealedOriginal) => void;
  onHide: () => void;
};

/**
 * Reveals the readable original (signatures visible) for the document panel to
 * show in place of the masked pages. Each reveal is audited and fetches a fresh
 * link, so the link is never kept.
 */
function HostRevealOriginalButton({ caseId, doc, revealed, onReveal, onHide }: Props) {
  const { api } = useWonderful();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!doc.documentId) return null;
  const unavailable = doc.originalAvailable === false;

  const reveal = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.invokeFunction<OriginalResponse>("backoffice/document-original", {
        method: "POST",
        params: { case_id: caseId, document_id: doc.documentId },
      });
      if (result.error !== undefined) throw new Error(errorText[result.error] ?? `Couldn't reveal the original (${result.error}).`);
      onReveal({ url: result.url, filename: result.filename, contentType: result.contentType, pages: result.pages ?? [] });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (revealed) {
    return (
      <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={onHide}>
        Hide original
      </button>
    );
  }

  return (
    <span className="cr-reveal">
      <button
        type="button"
        className="kb-btn kb-btn--secondary kb-btn--small"
        onClick={reveal}
        disabled={busy || unavailable}
        title={unavailable ? "No original for this document" : "Shows the original with readable signatures. The reveal is audited."}
      >
        {busy ? "Revealing…" : "Reveal original"}
      </button>
      {error && (
        <span className="cr-reveal__error" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}

// The plain Vite dev server has no Wonderful host to call the Function through.
function LocalRevealOriginalButton({ doc }: Props) {
  if (!doc.documentId) return null;
  return (
    <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" disabled title="Needs the Wonderful host">
      Reveal original
    </button>
  );
}

// import.meta.env.DEV is a build-time constant, so the hook order never changes.
const RevealOriginalButton = import.meta.env.DEV ? LocalRevealOriginalButton : HostRevealOriginalButton;

export default RevealOriginalButton;
