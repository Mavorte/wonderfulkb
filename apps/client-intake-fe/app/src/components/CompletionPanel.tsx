import { useEffect, useRef } from "react";
import type { UploadedDocument } from "../types";
import KbIcon from "./KbIcon";

// Shown after a successful upload, so the client knows they are done.
export default function CompletionPanel({
  documents,
  onUploadMore,
}: {
  documents: UploadedDocument[];
  onUploadMore: () => void;
}) {
  const ref = useRef<HTMLElement>(null);

  // The upload card sits low on the page; start the client at this message.
  useEffect(() => {
    ref.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    ref.current?.focus({ preventScroll: true });
  }, []);

  const count = documents.length;

  return (
    <section ref={ref} className="app-card app-done app-status" role="status" tabIndex={-1}>
      <KbIcon name="check" className="app-done__icon" />
      <h2 className="app-done__title">You're all set</h2>
      <p className="app-done__text">
        Komerční banka has received {count === 1 ? "your document" : `your ${count} documents`}. There is nothing
        else you need to do, and you can close this page. Your KB advisor will contact you if anything more is needed.
      </p>
      {count > 0 && (
        <div className="app-stack app-received app-done__list">
          <h3 className="app-received__title">Received from you</h3>
          <ul className="app-list">
            {documents.map((doc) => (
              <li key={doc.document_id}>
                <KbIcon name="check" className="app-list__ok" />
                <span className="app-files__name">{doc.filename}</span>
                <span className="app-list__meta">{new Date(doc.received_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <button type="button" className="kb-btn kb-btn--secondary" onClick={onUploadMore}>
        <KbIcon name="upload" />
        Upload more documents
      </button>
    </section>
  );
}
