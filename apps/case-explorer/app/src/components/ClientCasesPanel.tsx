import { Box, Button, Card, Col, Row, Stack, Table, Text, type ColumnDef } from "@wonderful/ui-base";
import type { Case, CellProps, Client } from "../types";
import { useFunctionResult } from "../useExplorerApi";
import UpstreamStatus from "./UpstreamStatus";

type CaseList = { client_id: string; cases: Case[]; next_token?: string | null };

function getColumns(onSelectCase: (caseId: string) => void): ColumnDef<Case, unknown>[] {
  return [
    {
      id: "case_id",
      header: "Case ID",
      cell: ({ row }: CellProps<Case>) => (
        <Box direction="row">
          <Button variant="link" size="small" onClick={() => onSelectCase(row.original.case_id)}>
            {row.original.case_id}
          </Button>
        </Box>
      ),
    },
    { id: "status", header: "Status", cell: ({ row }: CellProps<Case>) => row.original.status },
    { id: "created_at", header: "Created", cell: ({ row }: CellProps<Case>) => formatDate(row.original.created_at) },
  ];
}

// Client details, then GET /clients/{client_id}/cases.
export default function ClientCasesPanel({
  client,
  selectedCaseId,
  onSelectCase,
}: {
  client: Client;
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}) {
  const { isLoading, result } = useFunctionResult<CaseList>("client-cases", { client_id: client.client_id });
  const cases = result?.body?.cases ?? [];
  const columns = getColumns(onSelectCase);
  const contact = client.contacts?.find((c) => c.email || c.phone);
  const signatories = (client.signatories ?? []).map((s) => [s.name, s.function].filter(Boolean).join(", "));

  return (
    <Card title={client.name} padding={4}>
      <Stack gap={4}>
        <Row>
          <Col md={6}>
            <Stack gap={2}>
              <Field label="IČO / DIČ" value={[client.ico, client.dic].filter(Boolean).join(" / ")} />
              <Field label="Address" value={client.address} />
              <Field label="Client ID" value={client.client_id} />
            </Stack>
          </Col>
          <Col md={6}>
            <Stack gap={2}>
              <Field
                label="Contact"
                value={contact && [contact.name, contact.email, contact.phone].filter(Boolean).join(" · ")}
              />
              <Field label="Signatories" value={signatories.join("; ")} />
              <Field
                label="KYC"
                value={client.kyc && [client.kyc.status, client.kyc.checked_at].filter(Boolean).join(", ")}
              />
            </Stack>
          </Col>
        </Row>
        <Text variant="heading-4">Cases</Text>
        <Table
          data={cases}
          columns={columns}
          rowKey={(c) => c.case_id}
          activeRowKey={selectedCaseId ?? undefined}
          onRowClick={(c) => onSelectCase(c.case_id)}
          isLoading={isLoading && !result}
          isCompact
          emptyContent={
            result?.ok ? (
              <Text variant="body-sm" color="secondary">
                This client has no cases.
              </Text>
            ) : null
          }
          aria-label="Client cases"
        />
        <UpstreamStatus result={result} />
      </Stack>
    </Card>
  );
}

export function Field({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <Stack gap={1}>
      <Text variant="caption" color="tertiary">
        {label}
      </Text>
      <Text variant="body-sm">{value === undefined || value === null || value === "" ? "—" : String(value)}</Text>
    </Stack>
  );
}

export function formatDate(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
