import { Alert, Badge, Box, Button, Card, Modal, Stack, Table, Text, type BadgeColor, type ColumnDef } from "@wonderful/ui-base";
import { useEffect, useState } from "react";
import type { CellProps, Evaluation, EvaluationResult, UpstreamResult } from "../types";
import { useExplorerApi, useFunctionResult } from "../useExplorerApi";
import { formatDate } from "./ClientCasesPanel";
import UpstreamStatus from "./UpstreamStatus";

type EvaluationList = { case_id: string; evaluations: Evaluation[]; results: EvaluationResult[] };
type DeleteResult = { case_id: string; deleted: { evaluations: number; results: number } };
type RunResults = { evaluation_id: string; evaluation: Evaluation | null; results: EvaluationResult[] };

const POLL_MS = 3000;

const STATUS_COLORS: Record<string, BadgeColor> = {
  completed: "green",
  running: "blue",
  failed: "red",
  ready: "green",
  needs_correction: "red",
  needs_review: "orange",
  passed: "green",
  missing: "red",
  conflict: "red",
  cannot_verify: "orange",
};

function StatusBadge({ value }: { value?: string | null }) {
  if (!value) return <>—</>;
  return <Badge text={value} color={STATUS_COLORS[value] ?? "neutral"} variant="outlined" size="small" />;
}

function Clipped({ value }: { value?: string | number | null }) {
  if (value === undefined || value === null || value === "") return <>—</>;
  return (
    <span title={String(value)}>
      <Text variant="body-sm">{String(value).length > 160 ? `${String(value).slice(0, 160)}…` : String(value)}</Text>
    </span>
  );
}

function RunId({ id }: { id: string }) {
  return (
    <span title={id}>
      <Text variant="caption" color="tertiary">
        {id.length > 12 ? `${id.slice(0, 8)}…` : id}
      </Text>
    </span>
  );
}

const evaluationColumns: ColumnDef<Evaluation, unknown>[] = [
  {
    id: "evaluation_id",
    header: "Run",
    cell: ({ row }: CellProps<Evaluation>) => <RunId id={row.original.evaluation_id} />,
  },
  { id: "status", header: "Status", cell: ({ row }: CellProps<Evaluation>) => <StatusBadge value={row.original.status} /> },
  { id: "verdict", header: "Verdict", cell: ({ row }: CellProps<Evaluation>) => <StatusBadge value={row.original.verdict} /> },
  { id: "rules_total", header: "Rules", cell: ({ row }: CellProps<Evaluation>) => row.original.rules_total ?? "—" },
  { id: "is_mock", header: "Mock", cell: ({ row }: CellProps<Evaluation>) => (row.original.is_mock ? "yes" : "no") },
  { id: "started_at", header: "Started", cell: ({ row }: CellProps<Evaluation>) => formatDate(row.original.started_at ?? undefined) },
  { id: "finished_at", header: "Finished", cell: ({ row }: CellProps<Evaluation>) => formatDate(row.original.finished_at ?? undefined) },
  { id: "summary", header: "Summary", cell: ({ row }: CellProps<Evaluation>) => <Clipped value={row.original.summary} /> },
];

const resultColumns: ColumnDef<EvaluationResult, unknown>[] = [
  {
    id: "evaluation_id",
    header: "Run",
    cell: ({ row }: CellProps<EvaluationResult>) => <RunId id={row.original.evaluation_id} />,
  },
  { id: "rule_id", header: "Rule", cell: ({ row }: CellProps<EvaluationResult>) => row.original.rule_id },
  { id: "status", header: "Status", cell: ({ row }: CellProps<EvaluationResult>) => <StatusBadge value={row.original.status} /> },
  { id: "expected", header: "Expected", cell: ({ row }: CellProps<EvaluationResult>) => <Clipped value={row.original.expected} /> },
  { id: "found", header: "Found", cell: ({ row }: CellProps<EvaluationResult>) => <Clipped value={row.original.found} /> },
  { id: "reasoning", header: "Reasoning", cell: ({ row }: CellProps<EvaluationResult>) => <Clipped value={row.original.reasoning} /> },
  {
    id: "recorded_at",
    header: "Recorded",
    cell: ({ row }: CellProps<EvaluationResult>) => formatDate(row.original.recorded_at ?? undefined),
  },
];

// One run's results, polled every few seconds while it is selected. Unmounting stops the polling.
function RunResults({ evaluationId, onClose }: { evaluationId: string; onClose: () => void }) {
  const run = useFunctionResult<RunResults>("evaluation-results", { evaluation_id: evaluationId }, { pollMs: POLL_MS });
  const evaluation = run.result?.body?.evaluation;
  const results = run.result?.body?.results ?? [];
  const isLive = run.result?.ok ?? true;

  return (
    <Stack gap={3}>
      <Box direction="row" gap={2} align="center" justify="between" isWrapping>
        <Box direction="row" gap={2} align="center" isWrapping>
          <Text variant="caption" color="tertiary">
            case_evaluation_results for run
          </Text>
          <RunId id={evaluationId} />
          <StatusBadge value={evaluation?.status} />
          {evaluation?.verdict && <StatusBadge value={evaluation.verdict} />}
          <span className={`live-indicator${isLive ? "" : " is-paused"}`} title={`Polling every ${POLL_MS / 1000} s`}>
            <span className="live-dot" />
            <Text variant="caption" color={isLive ? "success" : "secondary"}>
              {isLive ? "Live" : "Poll failed, retrying"}
              {run.lastLoadedAt ? ` · updated ${run.lastLoadedAt.toLocaleTimeString()}` : ""}
            </Text>
          </span>
        </Box>
        <Button size="small" variant="text" startIcon="x" aria-label="Unselect run" title="Unselect run" onClick={onClose} />
      </Box>
      <Table
        data={results}
        columns={resultColumns}
        rowKey={(r) => `${r.evaluation_id}/${r.rule_id}`}
        isLoading={run.isLoading && !run.result}
        isCompact
        emptyContent={
          run.result?.ok ? (
            <Text variant="body-sm" color="secondary">
              No rule results for this run yet.
            </Text>
          ) : null
        }
        aria-label="Run evaluation results"
      />
      <UpstreamStatus result={run.result} />
    </Stack>
  );
}

// The case's rows in agent_functions.case_evaluations and case_evaluation_results,
// with a button that deletes all of them. Selecting a run shows only its results, live. Raw shows every column, including sources and details.
export default function EvaluationsPanel({ caseId }: { caseId: string }) {
  const call = useExplorerApi();
  const list = useFunctionResult<EvaluationList>("evaluations-list", { case_id: caseId });
  const [deletion, setDeletion] = useState<UpstreamResult<DeleteResult> | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  useEffect(() => {
    setDeletion(null);
    setSelectedRunId(null);
  }, [caseId]);

  const evaluations = list.result?.body?.evaluations ?? [];
  const results = list.result?.body?.results ?? [];
  const isEmpty = list.result?.ok && !evaluations.length && !results.length;

  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const deleteAll = async () => {
    setIsDeleting(true);
    const result = await call<DeleteResult>("evaluations-delete", { case_id: caseId });
    setDeletion(result);
    setIsDeleting(false);
    setIsConfirmOpen(false);
    setSelectedRunId(null);
    list.reload();
  };

  const emptyContent = (text: string) =>
    list.result?.ok ? (
      <Text variant="body-sm" color="secondary">
        {text}
      </Text>
    ) : null;

  return (
    <Card
      title={`Evaluations${list.result?.ok ? ` (${evaluations.length} runs, ${results.length} results)` : ""}`}
      actions={
        <Box direction="row" gap={1}>
          <Button size="small" variant="outlined" startIcon="trash" isDisabled={!list.result?.ok || isEmpty} onClick={() => setIsConfirmOpen(true)}>
            Delete all
          </Button>
          <Button size="small" variant="text" startIcon="arrow-clockwise" onClick={list.reload} />
        </Box>
      }
      padding={4}
    >
      <Modal
        open={isConfirmOpen}
        onClose={() => !isDeleting && setIsConfirmOpen(false)}
        title={`Delete evaluations of ${caseId}?`}
        size="small"
        footer={
          <Box direction="row" gap={2} justify="end">
            <Button variant="outlined" isDisabled={isDeleting} onClick={() => setIsConfirmOpen(false)}>
              Cancel
            </Button>
            <Button color="warning" startIcon="trash" isLoading={isDeleting} onClick={deleteAll}>
              Delete
            </Button>
          </Box>
        }
      >
        <Text variant="body-sm">
          This deletes {evaluations.length} run(s) and {results.length} rule result(s) for this case. It cannot be undone.
        </Text>
      </Modal>
      <Stack gap={3}>
        {deletion && (
          <Alert
            variant={deletion.ok ? "success" : "error"}
            title={
              deletion.ok && deletion.body
                ? `Deleted ${deletion.body.deleted.evaluations} run(s) and ${deletion.body.deleted.results} result(s)`
                : `Delete failed: ${deletion.error ?? `HTTP ${deletion.status}`}`
            }
            isClosable
            onClose={() => setDeletion(null)}
          />
        )}
        <Text variant="caption" color="tertiary">
          case_evaluations
        </Text>
        <Table
          data={evaluations}
          columns={evaluationColumns}
          rowKey={(e) => e.evaluation_id}
          activeRowKey={selectedRunId ?? undefined}
          onRowClick={(e) => setSelectedRunId((id) => (id === e.evaluation_id ? null : e.evaluation_id))}
          isLoading={list.isLoading && !list.result}
          isCompact
          emptyContent={emptyContent("No evaluator runs for this case.")}
          aria-label="Case evaluations"
        />
        {selectedRunId ? (
          <RunResults evaluationId={selectedRunId} onClose={() => setSelectedRunId(null)} />
        ) : (
          <>
            <Text variant="caption" color="tertiary">
              case_evaluation_results (all runs; select a run to see its results live)
            </Text>
            <Table
              data={results}
              columns={resultColumns}
              rowKey={(r) => `${r.evaluation_id}/${r.rule_id}`}
              isLoading={list.isLoading && !list.result}
              isCompact
              emptyContent={emptyContent("No rule results for this case.")}
              aria-label="Case evaluation results"
            />
          </>
        )}
        <UpstreamStatus result={list.result} />
      </Stack>
    </Card>
  );
}
