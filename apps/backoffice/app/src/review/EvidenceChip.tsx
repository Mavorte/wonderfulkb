import type { Focus } from "./DocumentPanel";

export interface CitedDoc {
  docKey: string;
  title: string;
  pages: number[];
}

export default function EvidenceChip({ source, onOpen }: { source: CitedDoc; onOpen: (focus: Focus) => void }) {
  return (
    <button
      type="button"
      className="cr-evidence"
      title={source.title}
      onClick={() => onOpen({ docKey: source.docKey, page: source.pages[0] ?? 1, nonce: Date.now() })}
    >
      <svg className="kb-icon kb-icon--16" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm4 18H6V4h7v5h5v11ZM8 12h8v2H8v-2Zm0 4h8v2H8v-2Z" />
      </svg>
      <span className="cr-evidence__src">
        {source.title.replace(/\.pdf$/i, "")}
        {source.pages.length > 0 && ` · p. ${source.pages.join(", ")}`}
      </span>
    </button>
  );
}
