import { Alert, Box, Button, Text } from "@wonderful/ui-base";
import { useState } from "react";
import type { UpstreamResult } from "../types";
import JsonBlock from "./JsonBlock";

// One line per upstream call: HTTP status, URL and key used, plus a toggle for
// the raw response. Failed calls show as an alert with the upstream's message.
export default function UpstreamStatus({ result }: { result: UpstreamResult | null }) {
  const [isRawOpen, setIsRawOpen] = useState(false);
  if (!result) return null;

  const statusText = result.status ? `HTTP ${result.status}` : "No response";
  const detail = [result.url, result.secret ? `key: ${result.secret}` : ""].filter(Boolean).join(" · ");

  return (
    <Box direction="column" gap={2}>
      {!result.ok && (
        <Alert
          variant="error"
          title={`${statusText}${result.error ? `: ${result.error}` : ""}`}
          description={getUpstreamMessage(result.body)}
        />
      )}
      <Box direction="row" gap={2} align="center" justify="between">
        <Text variant="caption" color="tertiary" truncate>
          {result.ok ? `${statusText} · ` : ""}
          {detail}
        </Text>
        <Button size="small" variant="text" onClick={() => setIsRawOpen((open) => !open)}>
          {isRawOpen ? "Hide raw" : "Raw"}
        </Button>
      </Box>
      {isRawOpen && <JsonBlock value={result.body} />}
    </Box>
  );
}

function getUpstreamMessage(body: unknown): string | undefined {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    const message = record.error ?? record.message;
    if (typeof message === "string") return message;
  }
  return typeof body === "string" && body ? body.slice(0, 300) : undefined;
}
