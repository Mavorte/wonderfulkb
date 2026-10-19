import json

from .blobs import AwsBlobs, LocalBlobs
from .repository import AwsRepository, Conflict, LocalRepository
from .service import DocumentService, now

CLIENTS = [
    {"client_id": "c0010000-0000-4000-8000-000000000001", "ico": "98007009", "dic": "CZ98007009",
     "name": "Dravonex Obrábění s.r.o.", "address": "Výrobní dvůr 126, 751 01 Rudoluh", "status": "active", "source": "synthetic"},
    {"client_id": "c0010000-0000-4000-8000-000000000002", "ico": "98007106", "dic": "CZ98007106",
     "name": "Agroluh Vřesava s.r.o.", "address": "Polní alej 143, 581 01 Olšovřes", "status": "active", "source": "synthetic"},
    {"client_id": "c0010000-0000-4000-8000-000000000003", "ico": "98001001", "dic": "CZ98001001",
     "name": "Kavorin Rec s.r.o.", "address": "U Třídicí haly 208, 739 61 Lipovřes", "status": "active", "source": "synthetic"},
]


def create_service(settings):
    if settings.provider not in ("local", "bedrock"):
        raise ValueError("OCR_PROVIDER must be local or bedrock")
    if settings.backend == "aws":
        import boto3
        if not all([settings.documents_table, settings.cases_table, settings.clients_table, settings.bucket, settings.queue_url]):
            raise ValueError("AWS storage requires table, bucket and queue configuration")
        sqs = boto3.client("sqs", region_name=settings.bedrock_region)
        def enqueue(job):
            sqs.send_message(QueueUrl=settings.queue_url, MessageBody=json.dumps({"job_id": job["job_id"]}))
        return DocumentService(settings, AwsRepository(settings), AwsBlobs(settings), enqueue)
    if settings.backend != "local":
        raise ValueError("STORAGE_BACKEND must be local or aws")
    repository = LocalRepository(settings.data_dir)
    for client in CLIENTS:
        try:
            repository.create("CLIENT#" + client["client_id"], "META", client)
        except Conflict:
            pass
    return DocumentService(settings, repository, LocalBlobs(settings.data_dir))
