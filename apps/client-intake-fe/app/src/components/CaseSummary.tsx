import { Badge, Card, Col, Icon, Row, Stack, Text } from "@wonderful/ui-base";
import type { IntakeData } from "../types";

type Field = { label: string; value: unknown };

function FieldList({ fields }: { fields: Field[] }) {
  const visible = fields.filter((f) => f.value !== undefined && f.value !== null && f.value !== "");
  if (visible.length === 0) {
    return (
      <Text variant="body-sm" color="secondary">
        No details available.
      </Text>
    );
  }
  return (
    <Stack gap={3}>
      {visible.map((f) => (
        <Stack gap={1} key={f.label}>
          <Text variant="label-sm" color="secondary">
            {f.label}
          </Text>
          <Text variant="body">{String(f.value)}</Text>
        </Stack>
      ))}
    </Stack>
  );
}

export default function CaseSummary({ data }: { data: IntakeData }) {
  const metadata = data.case.metadata ?? {};
  const requiredDocuments = Array.isArray(metadata.required_documents)
    ? (metadata.required_documents as unknown[]).map(String)
    : [];
  const client = data.client;

  return (
    <Stack gap={4}>
      <Row>
        <Col xs={12} md={6}>
          <Card padding={5} title="Case" actions={data.is_mock ? <Badge text="Demo data" color="orange" /> : undefined}>
            <FieldList
              fields={[
                { label: "Case ID", value: data.case.case_id },
                { label: "Loan agreement", value: metadata.loan_number },
                { label: "Financed asset", value: metadata.asset },
                { label: "Serial number", value: metadata.serial_number },
              ]}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card padding={5} title="Client">
            <FieldList
              fields={[
                { label: "Name", value: client?.name },
                { label: "IČO", value: client?.ico },
                { label: "DIČ", value: client?.dic },
                { label: "Address", value: client?.address },
              ]}
            />
          </Card>
        </Col>
      </Row>
      {requiredDocuments.length > 0 && (
        <Card padding={5} title="Documents we need from you">
          <Stack gap={2}>
            {requiredDocuments.map((doc) => (
              <Text variant="body" key={doc}>
                <Icon name="file-pdf" color="secondary" /> {doc}
              </Text>
            ))}
          </Stack>
        </Card>
      )}
    </Stack>
  );
}
