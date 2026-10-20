import { useWonderful } from "@wonderful/app-sdk";
import { type DragEvent, useEffect, useRef, useState } from "react";
import getIntakeHash from "../getIntakeHash";
import type { IntakeData, UploadedDocument } from "../types";
import uploadDocuments, { MAX_FILE_BYTES, type UploadProgress } from "../uploadDocuments";
import KbIcon from "./KbIcon";
import Notice from "./Notice";

type FileStatus = "waiting" | "sending" | "sent" | "failed";

const STATUS_LABELS: Record<FileStatus, string> = {
  waiting: "Waiting",
  sending: "Sending",
  sent: "Sent",
  failed: "Not sent",
};

function isPdf(file: File) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function formatSize(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function countFiles(count: number, noun = "file") {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}

function getFileStatus(index: number, progress: UploadProgress | null, failed: boolean): FileStatus | null {
  if (!progress) return failed ? "failed" : null;
  if (progress.phase === "submitting") return "sending";
  if (index < progress.index) return "sent";
  return index === progress.index ? "sending" : "waiting";
}

function FileStatusIcon({ status }: { status: FileStatus | null }) {
  if (status === "sending") return <span className="app-spinner" aria-hidden="true" />;
  if (status === "sent") return <KbIcon name="check" className="app-list__ok" />;
  if (status === "failed") return <KbIcon name="info" className="app-files__failed" />;
  return <KbIcon name="file" className="kb-icon--muted" />;
}

// Staging counts one step per file and the hand-off to ingest one more, so the
// bar never reads 100% before KB has the files.
function UploadProgressBar({ progress, total }: { progress: UploadProgress; total: number }) {
  const done = progress.phase === "staging" ? progress.index : total;
  const percent = Math.round((done / (total + 1)) * 100);
  const label =
    progress.phase === "staging"
      ? `Uploading file ${progress.index + 1} of ${total}`
      : `Sending ${countFiles(total)} to Komerční banka`;
  return (
    <div className="app-progress" role="status">
      <div className="app-progress__label">
        <span>{label}…</span>
        <span className="app-list__meta">{percent}%</span>
      </div>
      <div className="app-progress__track">
        <div className="app-progress__bar" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default function UploadPanel({
  data,
  uploaded,
  onUploaded,
}: {
  data: IntakeData;
  uploaded: UploadedDocument[];
  onUploaded: (documents: UploadedDocument[]) => void;
}) {
  const { api, track } = useWonderful();
  const inputRef = useRef<HTMLInputElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [rejected, setRejected] = useState<string[]>([]);
  const [tooLarge, setTooLarge] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [failedFile, setFailedFile] = useState<File | null>(null);
  const isUploading = progress !== null;

  // Bring the progress or error into view when an upload starts and when it fails.
  useEffect(() => {
    statusRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [isUploading, error]);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming || isUploading) return;
    const list = Array.from(incoming);
    setRejected(list.filter((f) => !isPdf(f)).map((f) => f.name));
    setTooLarge(list.filter((f) => isPdf(f) && f.size > MAX_FILE_BYTES).map((f) => f.name));
    setError(null);
    setFailedFile(null);
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
    setError(null);
    setFailedFile(null);
    setProgress({ phase: "staging", index: 0 });
    track("upload_started", { file_count: files.length });
    const result = await uploadDocuments(api, getIntakeHash(), files, data.client?.email, setProgress);
    setProgress(null);
    if (result.ok) {
      track("upload_completed", { file_count: result.documents.length });
      // Ingest normally lists what it stored; fall back to the sent files.
      const receivedAt = new Date().toISOString();
      const documents = result.documents.length
        ? result.documents
        : files.map((file) => ({
            document_id: file.name,
            filename: file.name,
            received_at: receivedAt,
            content_type: file.type,
            size_bytes: file.size,
          }));
      setFiles([]);
      onUploaded(documents);
    } else {
      track("upload_failed");
      setError(result.message);
      setFailedFile(result.failedFile ?? null);
    }
  };

  const canUpload = data.can_upload && files.length > 0;

  return (
    <section className="app-card">
      <div className="app-card__head">
        <h2 className="app-card__title">Upload documents</h2>
        {uploaded.length > 0 && (
          <span className="app-badge app-badge--success">
            <KbIcon name="check" className="kb-icon--16" />
            {countFiles(uploaded.length, "document")} received
          </span>
        )}
      </div>
      <div className="app-stack">
        {!data.can_upload && (
          <Notice
            variant="warning"
            title="Uploads are not available yet"
            description="The document service is not configured. Please try again later."
          />
        )}

        {(progress || error) && (
          <div ref={statusRef} className="app-stack app-status" key={error ? "error" : "progress"}>
            {progress && <UploadProgressBar progress={progress} total={files.length} />}
            {error && (
              <Notice
                variant="error"
                title="Upload failed, your documents were not sent"
                description={`${error} Your files are still listed below.`}
              />
            )}
          </div>
        )}

        <div
          className={`dropzone${isDragging ? " dropzone--active" : ""}${isUploading ? " dropzone--disabled" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            if (!isUploading) setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
        >
          <KbIcon name="upload" className="kb-icon--32 kb-icon--accent" />
          <div className="dropzone__text">
            <p>Drop PDF files here</p>
            <p className="dropzone__hint">or browse your device</p>
          </div>
          <button
            type="button"
            className="kb-btn kb-btn--secondary kb-btn--small"
            disabled={isUploading}
            onClick={() => inputRef.current?.click()}
          >
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
            {files.map((file, index) => {
              const status = getFileStatus(index, progress, file === failedFile);
              return (
                <li key={file.name} className={status === "failed" ? "is-failed" : undefined}>
                  <FileStatusIcon status={status} />
                  <span className="app-files__name">{file.name}</span>
                  <span className="app-list__meta">{status ? STATUS_LABELS[status] : formatSize(file.size)}</span>
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
              );
            })}
          </ul>
        )}

        {uploaded.length > 0 && (
          <div className="app-stack app-received">
            <h3 className="app-received__title">Received from you</h3>
            <ul className="app-list">
              {uploaded.map((doc) => (
                <li key={doc.document_id}>
                  <KbIcon name="check" className="app-list__ok" />
                  <span className="app-files__name">{doc.filename}</span>
                  <span className="app-list__meta">{new Date(doc.received_at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
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
    </section>
  );
}
