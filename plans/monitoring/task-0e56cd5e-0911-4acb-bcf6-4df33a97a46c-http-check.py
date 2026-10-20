"""One reserved read-only discovery GET; credentials never leave process memory.

Run only after reserving the request in this task's evidence ledger.
This is task evidence tooling, not a deployment or fixture creation interface.
"""
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None


def main():
    session = boto3.Session(profile_name="ai-hackathon", region_name="eu-central-1")
    try:
        assert session.client("sts").get_caller_identity()["Account"] == "609394381050"
        arn = "arn:aws:apprunner:eu-central-1:609394381050:service/wonderfulkb-ingest/c9ef96fae3da4192abd7e8280d43ae6b"
        service = session.client("apprunner").describe_service(ServiceArn=arn)["Service"]
        assert service["Status"] == "RUNNING"
        host = service["ServiceUrl"]
        assert host.endswith(".eu-central-1.awsapprunner.com") and "/" not in host
        assert service["SourceConfiguration"]["ImageRepository"]["ImageIdentifier"].endswith(":task-1d77ce99-e462d804")
        secrets = session.client("secretsmanager")
        def secret(name):
            return secrets.get_secret_value(SecretId=name, VersionStage="AWSCURRENT")
        api_key = secret("wonderfulkb/ingest-api-key")["SecretString"]
        bearer = secret("wonderfulkb/monitoring-synthetic-bearer-20261020")["SecretString"]
        policy_response = secret("wonderfulkb/monitoring-synthetic-20261020")
        policy = json.loads(policy_response["SecretString"])
        assert policy["schema_version"] == 1
        bindings = [c for c in policy["credentials"] if c["sha256"] == hashlib.sha256(bearer.encode()).hexdigest()]
        assert len(bindings) == 1 and bindings[0]["state"] == "active"
        case_id, document_id = "SYN-A01", "34fcd896-107a-583f-a406-6a8100cf8150"
        assert any(g["case_id"] == case_id and any(d["document_id"] == document_id and d["membership"] == "current"
                   for d in g["documents"]) for g in bindings[0]["grants"])
        path = f"/v1/cases/{case_id}/processing/documents/{document_id}/events?limit=50"
        request = urllib.request.Request("https://" + host + path,
                    headers={"x-api-key": api_key, "Authorization": "Bearer " + bearer})
        opener = urllib.request.build_opener(NoRedirect())
        evidence = {"time": datetime.now(timezone.utc).isoformat(), "host": host, "path": path,
                    "policy_version": policy_response["VersionId"], "active_hash_and_exact_grant": True,
                    "requests": 1, "writes": 0}
        try:
            response = opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            evidence.update(status=error.code, cache_control=error.headers.get("Cache-Control"))
            error.close()
        else:
            with response:
                body = json.load(response)
                evidence.update(status=response.status, cache_control=response.headers.get("Cache-Control"),
                                item_count=len(body["items"]), coverage=body.get("coverage"),
                                has_continuation=body.get("next_token") is not None,
                                reuse_ids=[{k: row[k] for k in ("event_id", "run_id", "attempt_no")}
                                           for row in body["items"] if row.get("type") == "PageCacheReused"])
        print(json.dumps(evidence, sort_keys=True))
        return 0
    except ClientError as error:
        print(json.dumps({"error": error.response["Error"]["Code"], "category": "AWS preflight", "http_started": False}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
