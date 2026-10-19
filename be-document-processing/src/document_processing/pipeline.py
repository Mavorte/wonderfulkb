import threading
import time
from uuid import uuid4

from . import PIPELINE_VERSION, PROMPT_VERSION
from .blobs import get_sha256
from .extraction import LocalExtractor
from .models import DocumentResult, Page
from .providers import LocalOcr, ProviderError
from .rendering import open_document, render_page
from .repository import Conflict
from .service import now


class DocumentWorker:
    def __init__(self, service, ocr=None, extractor=None):
        self.service, self.settings = service, service.settings
        self.repo, self.blobs = service.repo, service.blobs
        self.ocr = ocr or LocalOcr()
        self.extractor = extractor or LocalExtractor()
        if self.settings.provider == "bedrock":
            from .bedrock import BedrockExtractor, BedrockOcr
            from .pdf_first import PdfFirstOcr
            self.ocr = ocr or PdfFirstOcr(BedrockOcr(self.settings))
            self.extractor = extractor or BedrockExtractor(self.settings, self.ocr.client)

    def process(self, job_id):
        pending = self.repo.get("JOBS", job_id)
        if not pending:
            return
        document = self.service.get_document(pending["case_id"], pending["document_id"])
        if document.get("job_id") != job_id:
            # The local poller may see the job just before complete_upload links it.
            return
        owner, started = uuid4().hex, time.monotonic()
        def claim(job):
            if job["status"] in ("completed", "partial", "failed"):
                raise Conflict("finished")
            if job["status"] == "processing" and job["lease_until"] > time.time():
                raise Conflict("leased")
            if job["attempts"] >= self.settings.max_attempts:
                job.update(status="failed", error="MAX_ATTEMPTS_EXCEEDED")
                return job
            job.update(status="processing", owner=owner, lease_until=time.time() + self.settings.lease_seconds,
                       attempts=job["attempts"] + 1)
            return job
        try:
            job = self.repo.update("JOBS", job_id, claim)
        except Conflict:
            return
        case_id, document_id = job["case_id"], job["document_id"]
        if job["status"] == "failed":
            self._document_state(case_id, document_id, "failed", error="MAX_ATTEMPTS_EXCEEDED")
            return
        self._document_state(case_id, document_id, "processing")
        document = self.service.get_document(case_id, document_id)
        errors, pages, retryable = [], [], False
        result_key = f"results/{case_id}/{document_id}/{job['run_id']}/{owner}/result.json"
        try:
            expected = {"provider": self.settings.provider, "ocr_model": self.settings.ocr_model,
                        "extraction_model": self.settings.extraction_model, "mode": document["mode"],
                        "pipeline_version": PIPELINE_VERSION, "prompt_version": PROMPT_VERSION}
            expected.update(bedrock_api=self.settings.bedrock_api, bedrock_region=self.settings.bedrock_region)
            if job["config"] != expected:
                raise ProviderError("PIPELINE_CONFIG_CHANGED")
            body = self.blobs.read(document["source_key"], job["source_version"])
            if get_sha256(body) != job["source_sha256"]:
                raise ProviderError("SOURCE_HASH_MISMATCH")
            with open_document(body, document["content_type"], self.settings.max_pages) as pdf:
                for index, source in enumerate(pdf):
                    number = index + 1
                    preview_key = f"previews/{case_id}/{document_id}/{number}.png"
                    try:
                        self.blobs.head(preview_key)
                    except Exception:
                        png, _, _ = render_page(source)
                        try:
                            self.blobs.put(preview_key, png, "image/png")
                        except FileExistsError:
                            pass
                    cache_key = f"cache/{job_id}/{job['config_hash']}/{number}.json"
                    try:
                        page = Page.model_validate(self.blobs.read_json(cache_key))
                    except Exception:
                        try:
                            if time.monotonic() - started > 420:
                                raise ProviderError("WORKER_TIME_BUDGET", True)
                            page = self.ocr.transcribe(source, number, document["mode"])
                            try:
                                self.blobs.put_json(cache_key, page.model_dump())
                            except FileExistsError:
                                pass
                        except ProviderError as error:
                            retryable = retryable or error.retryable
                            errors.append({"code": error.code, "page_number": number, "retryable": error.retryable})
                            page = Page(page_number=number, status="failed", method="vision", width=source.rect.width,
                                        height=source.rect.height, text="", error=error.code)
                    pages.append(page)
                    self.repo.update("JOBS", job_id, lambda current: self._owned(current, owner, lease_until=time.time() + self.settings.lease_seconds))
            completed = [p for p in pages if p.status == "completed"]
            extraction = {"schema_version": "1.0", "document_type": "unknown", "fields": [], "warnings": [], "model": None}
            if completed:
                try:
                    extraction = self.extractor.extract(completed)
                except ProviderError as error:
                    retryable = retryable or error.retryable
                    errors.append({"code": error.code, "page_number": None, "retryable": error.retryable})
            status = "completed" if not errors else "partial" if completed else "failed"
            result = {"schema_version": "1.0", "case_id": case_id, "client_id": document["client_id"],
                      "document_id": document_id, "run_id": job["run_id"], "source_sha256": job["source_sha256"],
                      "page_count": len(pages), "processing_status": status,
                      "ocr": {"pages": [p.model_dump() for p in pages]}, "extraction": extraction,
                      "errors": errors, "processing": {"pipeline_version": PIPELINE_VERSION,
                          "prompt_version": PROMPT_VERSION, "config": job["config"],
                          "ocr_models": sorted({p.model for p in pages if p.model}),
                          "extraction_model": extraction.get("model"), "attempt": job["attempts"],
                          "elapsed_seconds": round(time.monotonic() - started, 3), "completed_at": now()}}
            result = DocumentResult.model_validate(result).model_dump()
            self.blobs.put_json(result_key, result)
            final_status = "queued" if retryable and job["attempts"] < self.settings.max_attempts else status
            self.repo.update("JOBS", job_id, lambda current: self._owned(current, owner, status=final_status, lease_until=0))
            self._document_state(case_id, document_id, final_status, result_key=result_key,
                                 document_type=extraction["document_type"], errors=errors)
            if final_status == "queued":
                self.service.enqueue(self.repo.get("JOBS", job_id))
        except Conflict:
            # An expired worker is fenced out and cannot publish over its successor.
            return
        except Exception as error:
            code = error.code if isinstance(error, ProviderError) else "PROCESSING_FAILED"
            is_retryable = error.retryable if isinstance(error, ProviderError) else True
            final_status = "queued" if is_retryable and job["attempts"] < self.settings.max_attempts else "failed"
            try:
                self.repo.update("JOBS", job_id, lambda current: self._owned(current, owner, status=final_status, lease_until=0, error=code))
            except Conflict:
                return
            self._document_state(case_id, document_id, final_status, error=code)
            if final_status == "queued":
                self.service.enqueue(self.repo.get("JOBS", job_id))

    def _owned(self, current, owner, **values):
        if current.get("owner") != owner:
            raise Conflict("lease lost")
        return {**current, **values}

    def _document_state(self, case_id, document_id, status, **values):
        self.repo.update("CASE#" + case_id, "DOC#" + document_id,
                         lambda current: {**current, "processing_status": status, "updated_at": now(), **values})


def start_local_worker(worker):
    stop = threading.Event()
    def run():
        while not stop.is_set():
            try:
                for job in worker.repo.list("JOBS"):
                    if stop.is_set():
                        break
                    if job["status"] == "queued" or (job["status"] == "processing" and job["lease_until"] < time.time()):
                        worker.process(job["job_id"])
            except Exception:
                # A temporary storage failure must not kill the polling thread.
                import logging
                logging.getLogger(__name__).warning("Local worker storage operation failed; retrying")
            finally:
                stop.wait(0.4)
    thread = threading.Thread(target=run, daemon=True, name="document-worker")
    thread.start()
    return stop, thread
