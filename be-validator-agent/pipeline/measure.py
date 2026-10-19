"""Counts AWS and Bedrock calls and times every document of a batch; used by `--report` of the CLI."""
import collections
import json
import logging
import time

import botocore.client
import httpx

from . import run as run_module


class Meter:
    def __init__(self, path=None):
        self.path = path
        self.counts = collections.Counter()
        self.documents = []
        self._installed = None

    def install(self):
        meter, original_call, original_send = self, botocore.client.BaseClient._make_api_call, httpx.Client.send

        def counted(client, operation, params):
            meter.counts[f"{client.meta.service_model.service_name}.{operation}"] += 1
            return original_call(client, operation, params)

        def send(client, request, **kwargs):
            meter.counts["bedrock-mantle.chat" if "bedrock-mantle" in request.url.host else f"http.{request.url.host}"] += 1
            return original_send(client, request, **kwargs)

        original_run = run_module.run_document

        def timed(case_id, document_id=None, **kwargs):
            before, started = collections.Counter(meter.counts), time.monotonic()
            row = original_run(case_id, document_id, **kwargs)
            meter.documents.append({
                "case_id": case_id, "document_id": row.get("document_id"), "title": row.get("title"),
                "status": row["processing_status"], "pages": int(row.get("page_count", 0)),
                "seconds": round(time.monotonic() - started, 1),
                "calls": {k: v - before[k] for k, v in meter.counts.items() if v - before[k]},
                "label": row.get("label"), "confidence": float(row["confidence"]) if "confidence" in row else None,
                "description": row.get("description"), "pages_failed": sorted(int(p) for p in row.get("pages_failed", []))})
            last = meter.documents[-1]
            logging.getLogger("pipeline").info("%s %s %.0fs %s %s", case_id, last["status"], last["seconds"], last["label"], last["title"])
            if meter.path:
                meter.save(meter.path)
            return row

        botocore.client.BaseClient._make_api_call, httpx.Client.send, run_module.run_document = counted, send, timed
        self._installed = (original_call, original_send, original_run)

    def save(self, path):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"documents": self.documents, "totals": dict(self.counts)}, handle, ensure_ascii=False, indent=1)
