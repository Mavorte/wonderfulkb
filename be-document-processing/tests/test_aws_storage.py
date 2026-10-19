"""Exercise the cloud storage/queue adapters without an AWS account or inference."""
import boto3
import pytest
from moto import mock_aws

from document_processing.bootstrap import CLIENTS, create_service
from document_processing.config import Settings
from document_processing.models import UploadRequest
from document_processing.pipeline import DocumentWorker
from document_processing.service import ServiceError
from conftest import make_pdf


@mock_aws
def test_cloud_upload_pins_s3_version_queues_and_persists_result():
    region = "eu-central-1"
    dynamodb = boto3.resource("dynamodb", region_name=region)
    for name, keys in (("documents", ("pk", "sk")), ("cases", ("case_id",)), ("clients", ("client_id",))):
        dynamodb.create_table(
            TableName=name, BillingMode="PAY_PER_REQUEST",
            KeySchema=[{"AttributeName": k, "KeyType": "HASH" if i == 0 else "RANGE"} for i, k in enumerate(keys)],
            AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in keys],
        )
    dynamodb.Table("clients").put_item(Item=CLIENTS[0])
    dynamodb.Table("cases").put_item(Item={"case_id": "case-aws", "client_id": CLIENTS[0]["client_id"]})
    s3 = boto3.client("s3", region_name=region)
    s3.create_bucket(Bucket="offline-document-test", CreateBucketConfiguration={"LocationConstraint": region})
    s3.put_bucket_versioning(Bucket="offline-document-test", VersioningConfiguration={"Status": "Enabled"})
    sqs = boto3.client("sqs", region_name=region)
    queue = sqs.create_queue(QueueName="offline-document-test")["QueueUrl"]
    service = create_service(Settings(backend="aws", provider="local", worker_enabled=False,
                                     documents_table="documents", cases_table="cases", clients_table="clients",
                                     bucket="offline-document-test", queue_url=queue))
    body = make_pdf("Smlouva o uveru cislo 123/26\nJistina 1000,00 CZK")
    upload = service.create_upload("case-aws", UploadRequest(filename="a.pdf", content_type="application/pdf", size_bytes=len(body)))
    document_id = upload["document"]["document_id"]
    with pytest.raises(ServiceError, match="UPLOAD_NOT_FOUND"):
        service.complete_upload("case-aws", document_id)
    document = service.get_document("case-aws", document_id)
    version = service.blobs.put(document["source_key"], body)["version_id"]
    with pytest.raises(FileExistsError):
        service.blobs.put(document["source_key"], b"overwrite")
    job = service.complete_upload("case-aws", document_id)
    assert service.repo.get("JOBS", job["job_id"])["source_version"] == version
    assert sqs.receive_message(QueueUrl=queue)["Messages"][0]["Body"]
    # Even if another object version appears, processing must read the pinned one.
    s3.put_object(Bucket="offline-document-test", Key=document["source_key"], Body=b"later version")
    DocumentWorker(service).process(job["job_id"])
    result = service.get_result("case-aws", document_id)
    assert result["processing_status"] == "completed"
    assert result["ocr"]["pages"][0]["method"] == "native"
    assert "123/26" in result["ocr"]["pages"][0]["text"]
    assert service.repo.list("CASE#case-aws", "DOC#")[0]["document_id"] == document_id
