import { Card, Stack, Text, ToggleGroup } from "@wonderful/ui-base";
import { useState } from "react";
import type { DocumentSummary, DocumentView } from "../types";
import { useFunctionResult } from "../useExplorerApi";
import { Field } from "./ClientCasesPanel";
import JsonBlock from "./JsonBlock";
import UpstreamStatus from "./UpstreamStatus";

// documents API `getDocumentForValidation`.
type ValidationDocument = DocumentSummary & { description?: string | null; text?: string; confidence?: number | null };

// One document from the documents API. Vectors and signatures are shown as raw JSON.
export default function DocumentPanel({ caseId, documentId }: { caseId: string; documentId: string }) {
  const [view, setView] = useState<DocumentView>("validation");
  const { result } = useFunctionResult<ValidationDocument>("document-get", {
    case_id: caseId,
    document_id: documentId,
    view,
  });
  const document = result?.ok && view === "validation" ? result.body : null;

  return (
    <Card
      title={document?.title ?? documentId}
      actions={
        <ToggleGroup value={view} onChange={(value) => setView(value as DocumentView)} size="small">
          <ToggleGroup.Item value="validation" text="Text" />
          <ToggleGroup.Item value="vectors" text="Vectors" />
          <ToggleGroup.Item value="signatures" text="Signatures" />
        </ToggleGroup>
      }
      padding={4}
    >
      <Stack gap={4}>
        {document && (
          <>
            <Field label="Label" value={[document.label, document.label_status].filter(Boolean).join(" · ")} />
            <Field label="Description" value={document.description} />
            {document.text && (
              <Stack gap={2}>
                <Text variant="caption" color="tertiary">
                  Text ({document.page_count ?? "?"} pages)
                </Text>
                <JsonBlock value={document.text} />
              </Stack>
            )}
          </>
        )}
        {result?.ok && view !== "validation" && <JsonBlock value={result.body} />}
        <UpstreamStatus result={result} />
      </Stack>
    </Card>
  );
}
