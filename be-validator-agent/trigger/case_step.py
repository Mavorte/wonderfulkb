"""Case-level step: `copy_suspicion` across the documents of one case.

The logic lives in `pipeline.copies.copy_case` (it rebuilds the ink masks from the stored detections, calls
`signature_pipeline.copycheck.mark_copies` and rewrites only the `copy_suspicion` of each finding in
signatures.json; no Textract or Bedrock call). This module only decides when it runs: the worker runs the
pipeline with `defer_copy_check=True`, so a document never starts the comparison itself, and queues one `case`
message when the last document of the case is in a final state. `copy_case` is idempotent, so a repeated or
concurrent case message does no harm, and a document added to the case later triggers it again."""
import json
import logging

log = logging.getLogger("trigger.case")


def run(case_id, options):
    from pipeline import copies
    result = copies.copy_case(case_id, options)
    log.info("case step %s", json.dumps(result, default=str))
    return result
