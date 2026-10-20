import { Alert, Box, Button, Modal, Text } from "@wonderful/ui-base";
import { useState } from "react";
import type { UpstreamResult } from "../types";
import { useExplorerApi } from "../useExplorerApi";

type ClearResult = { deleted: { evaluations: number; results: number } };

// Header button that deletes every row of case_evaluations and case_evaluation_results, for all cases,
// after a confirmation. A controlled Modal, because Modal.confirm throws in the app frame.
// `onCleared` lets the open case reload its list.
export default function ClearEvaluationsButton({ onCleared }: { onCleared: () => void }) {
  const call = useExplorerApi();
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [outcome, setOutcome] = useState<UpstreamResult<ClearResult> | null>(null);

  const clearAll = async () => {
    setIsClearing(true);
    const result = await call<ClearResult>("evaluations-clear");
    setOutcome(result);
    setIsClearing(false);
    setIsConfirmOpen(false);
    onCleared();
  };

  return (
    <>
      <Button variant="outlined" startIcon="trash" onClick={() => setIsConfirmOpen(true)}>
        Clear all evaluations
      </Button>
      <Modal
        open={isConfirmOpen}
        onClose={() => !isClearing && setIsConfirmOpen(false)}
        title="Delete all evaluations?"
        size="small"
        footer={
          <Box direction="row" gap={2} justify="end">
            <Button variant="outlined" isDisabled={isClearing} onClick={() => setIsConfirmOpen(false)}>
              Cancel
            </Button>
            <Button color="warning" startIcon="trash" isLoading={isClearing} onClick={clearAll}>
              Delete everything
            </Button>
          </Box>
        }
      >
        <Text variant="body-sm">
          This deletes every row of case_evaluations and case_evaluation_results, for all cases. It cannot be undone.
        </Text>
      </Modal>
      {outcome && (
        <Modal open onClose={() => setOutcome(null)} title="Clear all evaluations" size="small">
          <Alert
            variant={outcome.ok ? "success" : "error"}
            title={
              outcome.ok && outcome.body
                ? `Deleted ${outcome.body.deleted.evaluations} run(s) and ${outcome.body.deleted.results} result(s)`
                : `Clear failed: ${outcome.error ?? `HTTP ${outcome.status}`}`
            }
          />
        </Modal>
      )}
    </>
  );
}
