import json

from .api import create_app
from .bootstrap import create_service
from .config import Settings
from .pipeline import DocumentWorker

_adapter = None
_worker = None


def api_handler(event, context):
    global _adapter
    if _adapter is None:
        from mangum import Mangum
        _adapter = Mangum(create_app(), lifespan="off")
    # REST API stage /v1 is absent from event.path; internal local routes use /v1.
    event = dict(event)
    if not event.get("path", "").startswith("/v1/"):
        event["path"] = "/v1" + event.get("path", "/")
    return _adapter(event, context)


def worker_handler(event, context):
    global _worker
    if _worker is None:
        _worker = DocumentWorker(create_service(Settings.from_env()))
    failures = []
    for record in event.get("Records", []):
        try:
            _worker.process(json.loads(record["body"])["job_id"])
        except Exception:
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}
