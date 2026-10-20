import { useCallback, useEffect, useRef, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import type { DocView } from "./evaluation";

/** One document from the document-pages Function: masked pages only, never the readable original. */
type DocumentPreview =
  | {
      documentId: string;
      status: "ready";
      redacted: boolean;
      pdfUrl: string | null;
      pages: (string | null)[];
      originalAvailable: boolean;
    }
  | { documentId: string; status: "processing" }
  | { documentId: string; status: "not_found" }
  | { documentId: string; status: "error" };

type DocumentPagesResponse = { documents: DocumentPreview[]; error?: undefined } | { error: string };

type State =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; byId: Map<string, DocumentPreview> };

// The links are presigned for 300 s; a broken image refetches, at most this often.
const REFRESH_AFTER_MS = 30_000;

function unavailableReason(preview: DocumentPreview | undefined, state: Exclude<State, { status: "loading" }>): string {
  if (state.status === "error") return `Couldn't load the preview: ${state.message}`;
  if (!preview || preview.status === "not_found") return "The documents API doesn't have this document.";
  if (preview.status === "processing") return "The document is still being processed.";
  if (preview.status === "error") return "The documents API couldn't return this document's preview.";
  if (!preview.redacted) return "This document was processed before signature masking, so it has no masked preview.";
  return "None of this document's pages has a masked preview.";
}

/** Applies the previews to the documents that have a documents API id. */
function applyPreviews(docs: DocView[], state: State): DocView[] {
  return docs.map((doc): DocView => {
    if (!doc.documentId) return doc;
    const found = state.status === "ready" ? state.byId.get(doc.documentId) : undefined;
    const preview = found?.status === "ready" ? found : undefined;
    if (preview?.pages.some(Boolean)) {
      const { pages, pdfUrl, originalAvailable } = preview;
      return { ...doc, pages, pdf: pdfUrl ?? undefined, unavailable: undefined, originalAvailable };
    }
    // Keep a local preview (dev snapshot) over a "no preview" answer.
    if (doc.pages.length) return doc;
    if (state.status === "loading") return { ...doc, loading: true };
    return {
      ...doc,
      pdf: preview?.pdfUrl ?? undefined,
      unavailable: unavailableReason(found, state),
      originalAvailable: preview?.originalAvailable,
    };
  });
}

function useHostPreviews(caseId: string, docs: DocView[]): { docs: DocView[]; refresh: () => void } {
  const { api } = useWonderful();
  const [state, setState] = useState<State>({ status: "loading" });
  const [generation, setGeneration] = useState(0);
  const loadedAt = useRef(0);
  const loadedKey = useRef<string | null>(null);
  const ids = [...new Set(docs.map((d) => d.documentId).filter((id): id is string => !!id))];
  const idsKey = ids.join(",");

  useEffect(() => {
    if (!ids.length) {
      setState({ status: "ready", byId: new Map() });
      return;
    }
    let cancelled = false;
    // A new case or document set shows the loader; a link refresh keeps the current pages on screen.
    if (loadedKey.current !== `${caseId}|${idsKey}`) setState({ status: "loading" });
    loadedKey.current = `${caseId}|${idsKey}`;
    loadedAt.current = Date.now();
    api
      .invokeFunction<DocumentPagesResponse>("backoffice/document-pages", {
        method: "POST",
        params: { case_id: caseId, document_ids: ids },
      })
      .then((result) => {
        if (cancelled) return;
        if (result.error !== undefined) throw new Error(result.error);
        setState({ status: "ready", byId: new Map(result.documents.map((d) => [d.documentId, d])) });
      })
      .catch((e: unknown) => !cancelled && setState({ status: "error", message: e instanceof Error ? e.message : String(e) }));
    return () => {
      cancelled = true;
    };
    // `api` and `ids` are recreated each render; only the case, its documents or a refresh refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, idsKey, generation]);

  const refresh = useCallback(() => {
    if (Date.now() - loadedAt.current > REFRESH_AFTER_MS) setGeneration((g) => g + 1);
  }, []);

  return { docs: applyPreviews(docs, state), refresh };
}

// The plain Vite dev server has no Wonderful host; the snapshot's local previews stay as they are.
function useLocalPreviews(_caseId: string, docs: DocView[]) {
  return { docs, refresh: () => {} };
}

// import.meta.env.DEV is a build-time constant, so the hook order never changes.
const useDocumentPreviews: (caseId: string, docs: DocView[]) => { docs: DocView[]; refresh: () => void } =
  import.meta.env.DEV ? useLocalPreviews : useHostPreviews;

export default useDocumentPreviews;
