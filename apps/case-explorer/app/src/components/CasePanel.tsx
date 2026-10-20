import { Badge, Box, Button, Card, Col, Row, Stack, Table, Text, type ColumnDef } from "@wonderful/ui-base";
import { useEffect, useState } from "react";
import type { Case, CellProps, DocumentSummary } from "../types";
import { useFunctionResult } from "../useExplorerApi";
import { Field, formatDate } from "./ClientCasesPanel";
import DocumentPanel from "./DocumentPanel";
import EvaluationsPanel from "./EvaluationsPanel";
import JsonBlock from "./JsonBlock";
import UpstreamStatus from "./UpstreamStatus";

type DocumentList = { case_id: string; documents: DocumentSummary[]; next_token?: string | null };

function getColumns(onSelect: (documentId: string) => void): ColumnDef<DocumentSummary, unknown>[] {
  return [
    {
      id: "title",
      header: "Document",
      cell: ({ row }: CellProps<DocumentSummary>) => (
        <Box direction="column" align="start" gap={1}>
          <Button variant="link" size="small" onClick={() => onSelect(row.original.document_id)}>
            {row.original.title}
          </Button>
          <Text variant="caption" color="tertiary">
            {row.original.document_id}
          </Text>
        </Box>
      ),
    },
    {
      id: "label",
      header: "Label",
      cell: ({ row }: CellProps<DocumentSummary>) =>
        row.original.label ? (
          <Badge
            text={row.original.label}
            color={row.original.label_status === "verified" ? "green" : "neutral"}
            variant="outlined"
            size="small"
          />
        ) : (
          "—"
        ),
    },
    {
      id: "processing_status",
      header: "Processing",
      cell: ({ row }: CellProps<DocumentSummary>) => row.original.processing_status ?? "—",
    },
    {
      id: "page_count",
      header: "Pages",
      cell: ({ row }: CellProps<DocumentSummary>) => row.original.page_count ?? "—",
    },
  ];
}

// GET /cases/{case_id}, then the case's documents from the documents API.
export default function CasePanel({
  caseId,
  onOpenClient,
  onRunEvaluator,
  onClose,
}: {
  caseId: string;
  onOpenClient: (clientId: string) => void;
  onRunEvaluator: (caseId: string) => void;
  onClose: () => void;
}) {
  const caseResult = useFunctionResult<Case>("case-get", { case_id: caseId });
  const documents = useFunctionResult<DocumentList>("documents-list", { case_id: caseId });
  const [documentId, setDocumentId] = useState<string | null>(null);
  useEffect(() => setDocumentId(null), [caseId]);

  const caseData = caseResult.result?.ok ? caseResult.result.body : null;
  const documentRows = documents.result?.body?.documents ?? [];
  const columns = getColumns(setDocumentId);

  return (
    <Stack gap={4}>
      <Card
        title={`Case ${caseId}`}
        actions={
          <Box direction="row" gap={1}>
            <Button size="small" color="primary" startIcon="play" onClick={() => onRunEvaluator(caseId)}>
              Run evaluator
            </Button>
            <Button size="small" variant="text" startIcon="x" aria-label="Close case" title="Close case" onClick={onClose} />
          </Box>
        }
        padding={4}
      >
        <Stack gap={4}>
          {caseData && (
            <Row>
              <Col md={4}>
                <Field label="Status" value={caseData.status} />
              </Col>
              <Col md={4}>
                <Field label="Created" value={formatDate(caseData.created_at)} />
              </Col>
              <Col md={4}>
                <Stack gap={1}>
                  <Text variant="caption" color="tertiary">
                    Client
                  </Text>
                  <Button size="small" variant="link" onClick={() => onOpenClient(caseData.client_id)}>
                    {caseData.client_id}
                  </Button>
                </Stack>
              </Col>
            </Row>
          )}
          {caseData?.metadata && Object.keys(caseData.metadata).length > 0 && (
            <Stack gap={2}>
              <Text variant="caption" color="tertiary">
                Metadata
              </Text>
              <JsonBlock value={caseData.metadata} />
            </Stack>
          )}
          <UpstreamStatus result={caseResult.result} />
        </Stack>
      </Card>

      <Card
        title={`Documents${documents.result?.ok ? ` (${documentRows.length})` : ""}`}
        actions={<Button size="small" variant="text" startIcon="arrow-clockwise" onClick={documents.reload} />}
        padding={4}
      >
        <Stack gap={3}>
          <Table
            data={documentRows}
            columns={columns}
            rowKey={(d) => d.document_id}
            activeRowKey={documentId ?? undefined}
            onRowClick={(d) => setDocumentId(d.document_id)}
            isLoading={documents.isLoading && !documents.result}
            isCompact
            emptyContent={
              documents.result?.ok ? (
                <Text variant="body-sm" color="secondary">
                  No documents for this case.
                </Text>
              ) : null
            }
            aria-label="Case documents"
          />
          <UpstreamStatus result={documents.result} />
        </Stack>
      </Card>

      {documentId && <DocumentPanel caseId={caseId} documentId={documentId} />}

      <EvaluationsPanel caseId={caseId} />
    </Stack>
  );
}
