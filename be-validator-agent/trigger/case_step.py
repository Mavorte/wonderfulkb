"""Case-level step: `copy_suspicion` across the documents of one case.

The logic lives in `pipeline.copies.copy_case` (it rebuilds the ink masks from the stored detections, calls
`signature_pipeline.copycheck.mark_copies` and rewrites only the `copy_suspicion` of each finding in
signatures.json; no Textract or Bedrock call). This module only decides when it runs: the worker runs the
pipeline with `defer_copy_check=True`, so a document never starts the comparison itself, and queues one `case`
message when the last document of the case is in a final state. `copy_case` is idempotent, so a repeated or
concurrent case message does no harm, and a document added to the case later triggers it again.

After the copy check the case is handed to Wonderful: the webhook starts its evaluation agent and the case
moves to `evaluating`. Both happen only while the case is `open` or `intake_in_progress`, so a repeated case
message does not start a second evaluation. The webhook goes first: if it fails, the message is retried and
the status still allows the call; if the status write fails after it, a retry may call it once more."""
import json
import logging

from . import common, wonderful_webhook

log = logging.getLogger("trigger.case")


def run(case_id, options, ctx=None):
    from pipeline import copies
    copy_error = None
    try:
        result = copies.copy_case(case_id, options)
        log.info("case step %s", json.dumps(result, default=str))
    except Exception as error:  # noqa: BLE001 - the evaluation must not wait on the copy check; raised below
        log.exception("copy check of case %s failed", case_id)
        copy_error, result = error, {"case_id": case_id, "copy_check": "failed"}
    result["evaluation"] = start_evaluation(ctx or common.Context(), case_id)
    if copy_error is not None:
        raise copy_error
    return result


def start_evaluation(ctx, case_id):
    """Webhook to Wonderful, then the case -> evaluating. Returns what happened (for the log)."""
    case = ctx.get_case(case_id)
    if case is None:
        log.warning("case %s is not in the cases table, evaluation not started", case_id)
        common.emit_metric("CaseNotFound")
        return "no_case"
    if case.get("status") not in common.EVALUATE_FROM:
        return f"skipped ({case.get('status')})"
    if not wonderful_webhook.enabled():
        log.info("case %s: webhook disabled, status stays %s", case_id, case.get("status"))
        return "webhook_disabled"
    wonderful_webhook.start_evaluation(case_id)
    common.emit_metric("EvaluationStarted")
    common.set_case_status(ctx, case_id, "evaluating", common.EVALUATE_FROM)
    return "started"
