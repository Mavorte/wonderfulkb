import { Badge, Box, Button, Card, InputText, Stack, Table, Text, type ColumnDef } from "@wonderful/ui-base";
import { useEffect, useState } from "react";
import type { CellProps, Client } from "../types";
import { useFunctionResult } from "../useExplorerApi";
import UpstreamStatus from "./UpstreamStatus";

type ClientList = { clients: Client[]; next_token?: string | null };

const STATUS_COLORS: Record<string, "green" | "orange" | "red"> = {
  active: "green",
  inactive: "orange",
  blocked: "red",
};

function getColumns(onSelect: (client: Client) => void): ColumnDef<Client, unknown>[] {
  return [
    {
      id: "name",
      header: "Client",
      cell: ({ row }: CellProps<Client>) => (
        <Box direction="column" align="start" gap={1}>
          <Button variant="link" size="small" onClick={() => onSelect(row.original)}>
            {row.original.name}
          </Button>
          <Text variant="caption" color="tertiary">
            IČO {row.original.ico}
          </Text>
        </Box>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: ({ row }: CellProps<Client>) => (
        <Badge text={row.original.status} color={STATUS_COLORS[row.original.status] ?? "neutral"} size="small" />
      ),
    },
  ];
}

// GET /clients. Name and IČO filters go to the API; an 8-digit query is treated as an IČO.
export default function ClientsPanel({
  selectedClientId,
  onLoaded,
  onSelect,
}: {
  selectedClientId: string | null;
  onLoaded: (clients: Client[]) => void;
  onSelect: (client: Client) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Record<string, string>>({});
  const { isLoading, result, reload } = useFunctionResult<ClientList>("clients-list", filter);
  const clients = result?.body?.clients ?? [];
  const columns = getColumns(onSelect);
  useEffect(() => {
    if (result?.body?.clients) onLoaded(result.body.clients);
    // Report each loaded page once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const search = () => {
    const value = query.trim();
    if (!value) setFilter({});
    else if (/^\d{8}$/.test(value)) setFilter({ ico: value });
    else setFilter({ name: value });
  };

  return (
    <Card
      title={`Clients${result?.ok ? ` (${clients.length}${result.body?.next_token ? "+" : ""})` : ""}`}
      actions={<Button size="small" variant="text" startIcon="arrow-clockwise" onClick={reload} />}
      padding={4}
    >
      <Stack gap={3}>
        <InputText
          value={query}
          placeholder="Name or IČO, then Enter"
          startIcon="magnifying-glass"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <Table
          data={clients}
          columns={columns}
          rowKey={(client) => client.client_id}
          activeRowKey={selectedClientId ?? undefined}
          onRowClick={onSelect}
          isLoading={isLoading && !result}
          isCompact
          emptyContent={
            result?.ok ? (
              <Text variant="body-sm" color="secondary">
                No clients found.
              </Text>
            ) : null
          }
          aria-label="Clients"
        />
        <UpstreamStatus result={result} />
      </Stack>
    </Card>
  );
}
