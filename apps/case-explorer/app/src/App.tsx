import "./style.css";
import { useWonderful } from "@wonderful/app-sdk";
import { Alert, Box, Button, InputText, PageLayout, Stack, Text } from "@wonderful/ui-base";
import { useEffect, useRef, useState } from "react";
import CasePanel from "./components/CasePanel";
import ClientCasesPanel from "./components/ClientCasesPanel";
import ClientsPanel from "./components/ClientsPanel";
import UpstreamStatus from "./components/UpstreamStatus";
import type { Client, UpstreamResult } from "./types";
import { useExplorerApi } from "./useExplorerApi";

type EvaluatorRun = { caseId: string; result: UpstreamResult } | null;

const CLIENTS_OPEN_KEY = "case-explorer.clients-open";

function readClientsOpen(): boolean {
  try {
    return localStorage.getItem(CLIENTS_OPEN_KEY) !== "false";
  } catch {
    return true;
  }
}

export default function App() {
  const { track } = useWonderful();
  const call = useExplorerApi();
  const hasTrackedOpen = useRef(false);
  const knownClients = useRef(new Map<string, Client>());

  const [caseInput, setCaseInput] = useState("");
  const [client, setClient] = useState<Client | null>(null);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [run, setRun] = useState<EvaluatorRun>(null);
  const [isClientsOpen, setIsClientsOpen] = useState(readClientsOpen);

  const toggleClients = (isOpen: boolean) => {
    setIsClientsOpen(isOpen);
    try {
      localStorage.setItem(CLIENTS_OPEN_KEY, String(isOpen));
    } catch {
      // Storage may be blocked in the app frame; the toggle still works for this visit.
    }
  };

  useEffect(() => {
    if (hasTrackedOpen.current) return;
    hasTrackedOpen.current = true;
    track("explorer_opened");
  }, [track]);

  const openCase = (id: string) => {
    setCaseId(id);
    setCaseInput(id);
  };

  const runEvaluator = async (id: string) => {
    if (!id) return;
    setIsRunning(true);
    setRun(null);
    track("evaluator_run_started");
    const result = await call("evaluator-run", { case_id: id });
    track(result.ok ? "evaluator_run_completed" : "evaluator_run_failed", { status: result.status });
    setRun({ caseId: id, result });
    setIsRunning(false);
  };

  return (
    <div className="app-root">
      <PageLayout maxWidth={1600} padding={6}>
        <PageLayout.Header>
          <Box direction="row" gap={4} align="end" justify="between" isWrapping>
            <Stack gap={1}>
              <Text variant="heading-2">Case Explorer</Text>
              <Text variant="body-sm" color="secondary">
                AWS clients, cases and documents, and a manual trigger for the case evaluator.
              </Text>
            </Stack>
            <Box direction="row" gap={2} align="end">
              <InputText
                value={caseInput}
                placeholder="Case ID, e.g. SYN-A01"
                width={260}
                onChange={(e) => setCaseInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && caseInput.trim() && openCase(caseInput.trim())}
              />
              <Button
                variant="outlined"
                startIcon="folder-open"
                isDisabled={!caseInput.trim()}
                onClick={() => openCase(caseInput.trim())}
              >
                Open case
              </Button>
              <Button
                color="primary"
                startIcon="play"
                isLoading={isRunning}
                isDisabled={!caseInput.trim()}
                onClick={() => runEvaluator(caseInput.trim())}
              >
                Run evaluator
              </Button>
            </Box>
          </Box>
        </PageLayout.Header>
        <PageLayout.Content>
          <Stack gap={4}>
            {run && (
              <Alert
                variant={run.result.ok ? "success" : "error"}
                title={
                  run.result.ok
                    ? `Evaluator started for ${run.caseId} (HTTP ${run.result.status})`
                    : `Evaluator webhook failed for ${run.caseId}: ${run.result.error ?? `HTTP ${run.result.status}`}`
                }
                description={
                  <Stack gap={2}>
                    {getTaskSummary(run.result.body) && (
                      <Text variant="body-sm">{getTaskSummary(run.result.body)}</Text>
                    )}
                    <UpstreamStatus result={run.result} />
                  </Stack>
                }
                isClosable
                onClose={() => setRun(null)}
              />
            )}
            <div className="clients-layout">
              {isClientsOpen ? (
                <div className="clients-layout__side">
                  <ClientsPanel
                    selectedClientId={client?.client_id ?? null}
                    onLoaded={(clients) => clients.forEach((c) => knownClients.current.set(c.client_id, c))}
                    onSelect={(c) => {
                      setClient(c);
                      setCaseId(null);
                    }}
                    onCollapse={() => toggleClients(false)}
                  />
                </div>
              ) : (
                <div className="clients-rail">
                  <Button
                    size="small"
                    variant="text"
                    startIcon="caret-double-right"
                    aria-label="Show clients"
                    title="Show clients"
                    onClick={() => toggleClients(true)}
                  />
                  <span className="clients-rail__label">
                    <Text variant="caption" color="secondary">
                      {client ? `Clients · ${client.name}` : "Clients"}
                    </Text>
                  </span>
                </div>
              )}
              <div className="clients-layout__main">
                <Stack gap={4}>
                  {client && <ClientCasesPanel client={client} selectedCaseId={caseId} onSelectCase={openCase} />}
                  {caseId && (
                    <CasePanel
                      caseId={caseId}
                      onOpenClient={(id) => {
                        const known = knownClients.current.get(id);
                        if (known) setClient(known);
                      }}
                      onRunEvaluator={runEvaluator}
                      onClose={() => setCaseId(null)}
                    />
                  )}
                  {!client && !caseId && (
                    <Box direction="column" align="center" gap={3} padding={8}>
                      <Text variant="heading-4">Pick a client or open a case</Text>
                      <Text variant="body-sm" color="secondary">
                        Select a client on the left to see their cases, or type a case ID above.
                      </Text>
                    </Box>
                  )}
                </Stack>
              </div>
            </div>
          </Stack>
        </PageLayout.Content>
      </PageLayout>
    </div>
  );
}

// The webhook answers with the created task: `{ data: { id, status, ... } }`.
function getTaskSummary(body: unknown): string | null {
  const task = (body as { data?: { id?: string; status?: string } } | null)?.data;
  return task?.id
    ? `Task ${task.id}, status ${task.status ?? "unknown"}. The verdict lands in the task's resolution summary.`
    : null;
}
