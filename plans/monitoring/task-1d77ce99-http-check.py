"""One reserved, read-only TEST check; prints assertions, never credentials/content.

Do not rerun without reconciling the task HTTP ledger. This checks document
scope prerequisites only: it cannot invent a run when no observed ID is known.
"""
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError


SERVICE = "arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b"
CASE = "SYN-A01"
DOCUMENT = "34fcd896-107a-583f-a406-6a8100cf8150"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check():
    session = boto3.Session(profile_name="ai-hackathon", region_name="eu-central-1")
    assert session.client("sts").get_caller_identity()["Account"] == "609394381050"
    service = session.client("apprunner").describe_service(ServiceArn=SERVICE)["Service"]
    assert service["Status"] == "RUNNING"
    image = service["SourceConfiguration"]["ImageRepository"]["ImageIdentifier"]
    assert image.endswith("/wonderfulkb-ingest:task-1d77ce99-e462d804")
    host = service["ServiceUrl"]
    assert host.endswith(".eu-central-1.awsapprunner.com") and "/" not in host
    secrets = session.client("secretsmanager")

    def secret(name):
        return secrets.get_secret_value(SecretId=name, VersionStage="AWSCURRENT")

    api_key = secret("wonderfulkb/ingest-api-key")["SecretString"]
    bearer = secret("wonderfulkb/monitoring-synthetic-bearer-20261020")["SecretString"]
    policy_response = secret("wonderfulkb/monitoring-synthetic-20261020")
    policy = json.loads(policy_response["SecretString"])
    assert policy["schema_version"] == 1
    bindings = [entry for entry in policy["credentials"]
                if entry["sha256"] == hashlib.sha256(bearer.encode()).hexdigest()]
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding["state"] == "active" and binding["principal_type"] == "SERVICE"
    assert any(grant["case_id"] == CASE and any(
        document["document_id"] == DOCUMENT and document["membership"] == "current"
        for document in grant["documents"]) for grant in binding["grants"])
    print(json.dumps({"observed_at": datetime.now(timezone.utc).isoformat(),
                      "identity_account_verified": True, "image": image,
                      "host": host, "policy_version": policy_response["VersionId"],
                      "active_hash_binding_and_exact_current_grant": True}), flush=True)
    opener = urllib.request.build_opener(NoRedirect())
    path = f"/v1/cases/{CASE}/processing/documents/{DOCUMENT}/events"
    headers = {"x-api-key": api_key, "Authorization": "Bearer " + bearer}
    request = urllib.request.Request("https://" + host + path, headers=headers)
    try:
        response = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        status = response.code
        cache = response.headers.get("Cache-Control")
        # Never log response bodies, even on an unexpected status.
        print(json.dumps({"observed_at": datetime.now(timezone.utc).isoformat(),
                          "path": path, "status": status, "cache_control": cache,
                          "http_requests": 1, "writes": 0, "run_id_invented": False}), flush=True)
        assert cache == "private, no-store"
        if status == 404:
            print(json.dumps({"blocker": "Current-granted synthetic document is missing/masked; no observed run ID available. New run-events positive HTTP remains unverified."}))
            return 2
        assert status == 200
        body = json.load(response)
        assert set(body) == {"items", "next_token", "observed_at", "coverage"}
        assert body["coverage"] == "partial"
        assert all(item["case_id"] == CASE and item["document_id"] == DOCUMENT for item in body["items"])
        observed_runs = sorted({item["run_id"] for item in body["items"] if item.get("run_id")})
        print(json.dumps({"document_event_count": len(body["items"]),
                          "observed_run_ids": observed_runs,
                          "has_continuation": body["next_token"] is not None}))
        return 0 if observed_runs else 2


def main():
    try:
        return check()
    except ClientError as error:
        print(json.dumps({"aws_error": error.response["Error"]["Code"],
                          "operation": error.operation_name}))
        return 1
    except (BotoCoreError, AssertionError, ValueError, KeyError, urllib.error.URLError) as error:
        print(json.dumps({"check_error_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
