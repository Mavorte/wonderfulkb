import { useWonderful } from "@wonderful/app-sdk";
import { Alert, Box, Button, Card, Icon, Stack, Text } from "@wonderful/ui-base";
import { type DragEvent, useRef, useState } from "react";
import createUploadRequest from "../createUploadRequest";
import type { IntakeData, UploadedDocument } from "../types";

function isPdf(file: File) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function formatSize(bytes: number) {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function UploadPanel({ data }: { data: IntakeData }) {
  const { track } = useWonderful();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [rejected, setRejected] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploaded, setUploaded] = useState<UploadedDocument[]>([]);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const list = Array.from(incoming);
    setRejected(list.filter((f) => !isPdf(f)).map((f) => f.name));
    setError(null);
    setFiles((current) => {
      const names = new Set(current.map((f) => f.name));
      return [...current, ...list.filter((f) => isPdf(f) && !names.has(f.name))];
    });
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    addFiles(event.dataTransfer.files);
  };

  const onUpload = async () => {
    if (!data.upload || files.length === 0) return;
    setIsUploading(true);
    setError(null);
    track("upload_started", { file_count: files.length });
    const result = await createUploadRequest(data.upload, files, data.client?.email);
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

  return (
    <Card padding={5} title="Upload documents">
      <Stack gap={4}>
        {!data.upload && (
          <Alert
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
          <Box direction="column" align="center" gap={2} padding={6}>
            <Icon name="cloud-arrow-up" size={32} color="secondary" />
            <Text variant="body" align="center">
              Drag and drop PDF files here
            </Text>
            <Button variant="outlined" size="small" onClick={() => inputRef.current?.click()}>
              Choose files
            </Button>
          </Box>
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
          <Alert variant="warning" title="Only PDF files can be uploaded" description={`Skipped: ${rejected.join(", ")}`} />
        )}

        {files.length > 0 && (
          <Stack gap={2}>
            {files.map((file) => (
              <Box direction="row" align="center" justify="between" gap={3} key={file.name}>
                <Box direction="row" align="center" gap={2}>
                  <Icon name="file-pdf" color="secondary" />
                  <Text variant="body">{file.name}</Text>
                  <Text variant="body-sm" color="secondary">
                    {formatSize(file.size)}
                  </Text>
                </Box>
                <Button
                  variant="text"
                  size="small"
                  startIcon="x"
                  isDisabled={isUploading}
                  onClick={() => setFiles((current) => current.filter((f) => f !== file))}
                >
                  Remove
                </Button>
              </Box>
            ))}
          </Stack>
        )}

        {error && <Alert variant="error" title="Upload failed" description={error} />}

        <Box direction="row" justify="end">
          <Button
            color="primary"
            startIcon="upload-simple"
            isLoading={isUploading}
            isDisabled={!data.upload || files.length === 0}
            onClick={onUpload}
          >
            {files.length > 1 ? `Upload ${files.length} files` : "Upload"}
          </Button>
        </Box>

        {uploaded.length > 0 && (
          <Stack gap={2}>
            <Alert
              variant="success"
              title="Thank you, we received your documents"
              description="You can upload more files at any time using this link."
            />
            {uploaded.map((doc) => (
              <Box direction="row" align="center" gap={2} key={doc.document_id}>
                <Icon name="check-circle" color="success" />
                <Text variant="body">{doc.filename}</Text>
                <Text variant="body-sm" color="secondary">
                  {new Date(doc.received_at).toLocaleString()}
                </Text>
              </Box>
            ))}
          </Stack>
        )}
      </Stack>
    </Card>
  );
}
