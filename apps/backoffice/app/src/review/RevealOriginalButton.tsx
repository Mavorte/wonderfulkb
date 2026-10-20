import { useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import type { DocView } from "./evaluation";

type OriginalResponse = { url: string; filename: string; expiresIn: number; error?: undefined } | { error: string };

const errorText: Record<string, string> = {
  not_found: "The documents API has no original for this document.",
  unauthenticated: "Sign in to reveal the original.",
};

type Props = { caseId: string; doc: DocView };

/**
 * Opens the readable original (signatures visible) in a new tab. Each click is
 * audited and gets a fresh link that expires after 60 s, so the link is never kept.
 */
function HostRevealOriginalButton({ caseId, doc }: Props) {
  const { api } = useWonderful();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!doc.documentId) return null;
  const unavailable = doc.originalAvailable === false;

  const reveal = async () => {
    // Open the tab inside the click so popup blockers allow it; it gets the link once the call returns.
    // A blocked tab stops here, before the audited reveal.
    const tab = window.open("", "_blank");
    if (!tab) {
      setError("The browser blocked the new tab. Allow pop-ups for this app and try again.");
      return;
    }
    tab.opener = null;
    tab.document.title = "Opening original…";
    setBusy(true);
    setError(null);
    try {
      const result = await api.invokeFunction<OriginalResponse>("backoffice/document-original", {
        method: "POST",
        params: { case_id: caseId, document_id: doc.documentId },
      });
      if (result.error !== undefined) throw new Error(errorText[result.error] ?? `Couldn't reveal the original (${result.error}).`);
      tab.location.href = result.url;
    } catch (e: unknown) {
      tab.close();
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="cr-reveal">
      <button
        type="button"
        className="kb-btn kb-btn--secondary kb-btn--small"
        onClick={reveal}
        disabled={busy || unavailable}
        title={unavailable ? "No original for this document" : "Opens the original with readable signatures. The reveal is audited."}
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
