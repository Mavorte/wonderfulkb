import { useWonderful } from "@wonderful/app-sdk";
import { type DragEvent, useRef, useState } from "react";
import getIntakeHash from "../getIntakeHash";
import type { IntakeData, UploadedDocument } from "../types";
import uploadDocuments, { MAX_FILE_BYTES } from "../uploadDocuments";
import KbIcon from "./KbIcon";
import Notice from "./Notice";

function isPdf(file: File) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function formatSize(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function UploadPanel({ data }: { data: IntakeData }) {
  const { api, track } = useWonderful();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);
  const [tooLarge, setTooLarge] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<UploadedDocument[]>([]);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const list = Array.from(incoming);
    setRejected(list.filter((f) => !isPdf(f)).map((f) => f.name));
    setTooLarge(list.filter((f) => isPdf(f) && f.size > MAX_FILE_BYTES).map((f) => f.name));
    setError(null);
    setFiles((current) => {
      const names = new Set(current.map((f) => f.name));
      return [...current, ...list.filter((f) => isPdf(f) && f.size <= MAX_FILE_BYTES && !names.has(f.name))];
    });
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    addFiles(event.dataTransfer.files);
  };

  const onUpload = async () => {
    if (!data.can_upload || files.length === 0) return;
    setIsUploading(true);
    setError(null);
    track("upload_started", { file_count: files.length });
    const result = await uploadDocuments(api, getIntakeHash(), files, data.client?.email);
    setIsUploading(false);
    if (result.ok) {
      track("upload_completed", { file_count: result.documents.length });
      setUploaded((current) => [...result.documents, ...current]);
      setFiles([]);
    } else {
      track("upload_failed");
      setError(result.message);
    }
  };

  const canUpload = data.can_upload && files.length > 0;

  return (
    <section className="app-card">
      <div className="app-card__head">
        <h2 className="app-card__title">Upload documents</h2>
      </div>
      <div className="app-stack">
        {!data.can_upload && (
          <Notice
            variant="warning"
            title="Uploads are not available yet"
            description="The document service is not configured. Please try again later."
          />
        )}
        <div
          className={`dropzone${isDragging ? " dropzone--active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
        >
          <KbIcon name="upload" className="kb-icon--32 kb-icon--accent" />
          <div>
            <p>Drag and drop PDF files here</p>
            <p className="dropzone__hint">or choose them from your computer</p>
          </div>
          <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={() => inputRef.current?.click()}>
            Choose files
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            multiple
            hidden
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </div>

        {rejected.length > 0 && (
          <Notice variant="warning" title="Only PDF files can be uploaded" description={`Skipped: ${rejected.join(", ")}`} />
        )}

        {tooLarge.length > 0 && (
          <Notice
            variant="warning"
            title={`Files must be ${formatSize(MAX_FILE_BYTES)} or smaller`}
            description={`Skipped: ${tooLarge.join(", ")}`}
          />
        )}

        {files.length > 0 && (
          <ul className="app-files">
            {files.map((file) => (
              <li key={file.name}>
                <KbIcon name="file" className="kb-icon--muted" />
                <span className="app-files__name">{file.name}</span>
                <span className="app-list__meta">{formatSize(file.size)}</span>
                <button
                  type="button"
                  className="app-files__remove"
                  disabled={isUploading}
                  onClick={() => setFiles((current) => current.filter((f) => f !== file))}
                >
                  <KbIcon name="close" />
                  <span className="sr-only">Remove {file.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {error && <Notice variant="error" title="Upload failed" description={error} />}

        <div className="app-actions">
          <button
            type="button"
            className={`kb-btn kb-btn--primary${isUploading ? " is-loading" : ""}`}
            disabled={!canUpload || isUploading}
            aria-busy={isUploading}
            onClick={onUpload}
          >
            <KbIcon name="upload" />
            {files.length > 1 ? `Upload ${files.length} files` : "Upload"}
          </button>
        </div>

        {uploaded.length > 0 && (
          <>
            <Notice
              variant="success"
              title="Thank you, we received your documents"
              description="You can upload more files at any time using this link."
            />
            <ul className="app-list">
              {uploaded.map((doc) => (
                <li key={doc.document_id}>
                  <KbIcon name="check" className="app-list__ok" />
                  <span>{doc.filename}</span>
                  <span className="app-list__meta">{new Date(doc.received_at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
