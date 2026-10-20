"""Server-owned SERVICE credentials and exact case/document entitlements.

No allow cache: AWSCURRENT is fetched on every authenticated monitoring request.
Neither client claims nor audit rows establish document membership.
"""
import hashlib
import hmac
import json
import re
import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import boto3
from botocore.config import Config

from starlette.exceptions import HTTPException

from processing_monitor_lifecycle_routes import AuthorizedDocumentScope


IDENTIFIER = re.compile(r"^(?!\.{1,2}$)[A-Za-z0-9._-]{1,128}$")
BOUNDED_IO = Config(connect_timeout=1, read_timeout=2, retries={"total_max_attempts": 1})


class AuthorizationSecretSource:
    """Fresh server policy per request, without a last-known-good fallback."""

    def __init__(self, arn, client=None):
        self.arn, self.client = arn, client

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("PROCESSING_MONITOR_AUTHORIZATION_SECRET_ARN", ""))

    def __call__(self):
        if not isinstance(self.arn, str) or re.fullmatch(
                r"arn:aws:secretsmanager:eu-central-1:[0-9]{12}:secret:[A-Za-z0-9/_+=.@-]+", self.arn) is None:
            raise ValueError("monitor authorization is not configured")
        if self.client is None:
            self.client = boto3.client("secretsmanager", region_name="eu-central-1", config=BOUNDED_IO)
        response = self.client.get_secret_value(SecretId=self.arn, VersionStage="AWSCURRENT")
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate authorization field")
                result[key] = value
            return result
        policy = json.loads(response["SecretString"], object_pairs_hook=unique_object)
        # Preserve the already-installed lifecycle schema through one normalized
        # adapter. New deployments use the version/principals policy below.
        if isinstance(policy, dict) and "schema_version" in policy:
            return _normalize_lifecycle_policy(policy)
        return policy


def validate_identifier(value):
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise HTTPException(400, "invalid monitoring scope")
    return value


def _policy_identifier(value):
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise ValueError("invalid policy identifier")
    return value


def _fields(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("invalid authorization schema")


def _collection(value):
    if not isinstance(value, list) or len(value) > 1000:
        raise ValueError("invalid authorization collection")
    return value


@dataclass(frozen=True)
class AuthorizedCase:
    principal_id: str
    case_id: str
    retained_documents: frozenset[tuple[str, str]]
    allowed_documents: frozenset[tuple[str, str]] | None = None


def _validate_policy(policy):
    _fields(policy, ("version", "credentials", "principals", "retained_documents"))
    if type(policy["version"]) is not int or policy["version"] != 1:
        raise ValueError("unsupported authorization version")
    principals, bindings, retained = {}, {}, set()
    for principal in _collection(policy["principals"]):
        _fields(principal, ("id", "type", "enabled", "case_ids"))
        identifier = _policy_identifier(principal["id"])
        if (identifier in principals or principal["type"] != "SERVICE"
                or type(principal["enabled"]) is not bool):
            raise ValueError("invalid principal")
        grants = [_policy_identifier(case) for case in _collection(principal["case_ids"])]
        if len(grants) != len(set(grants)):
            raise ValueError("duplicate grant")
        principals[identifier] = (principal["enabled"], frozenset(grants))
    for binding in _collection(policy["credentials"]):
        _fields(binding, ("sha256", "principal_id"))
        digest = binding["sha256"]
        if (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or digest in bindings or _policy_identifier(binding["principal_id"]) not in principals):
            raise ValueError("invalid credential binding")
        bindings[digest] = binding["principal_id"]
    for record in _collection(policy["retained_documents"]):
        _fields(record, ("case_id", "document_id", "source_revision", "verified_at"))
        scope = (_policy_identifier(record["case_id"]), _policy_identifier(record["document_id"]))
        revision = record["source_revision"]
        if (scope in retained or not isinstance(revision, str)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,255}", revision) is None):
            raise ValueError("invalid retained provenance")
        verified_at = record["verified_at"]
        if not isinstance(verified_at, str) or "T" not in verified_at:
            raise ValueError("invalid verification time")
        if datetime.fromisoformat(verified_at.replace("Z", "+00:00")).utcoffset() != timedelta(0):
            raise ValueError("invalid verification time")
        retained.add(scope)
    return principals, bindings, frozenset(retained)


def authorize_case(source, authorization, case_id, *, mask_ungranted=False):
    """Authenticate identity and current case grant before any document/audit read."""
    validate_identifier(case_id)
    parts = (authorization or "").split(" ")
    if (len(parts) != 2 or parts[0].lower() != "bearer" or not 1 <= len(parts[1]) <= 512
            or re.fullmatch(r"[A-Za-z0-9._~+/-]+", parts[1]) is None):
        raise HTTPException(403, "case read access denied")
    try:
        policy = source()
        principals, bindings, retained = _validate_policy(policy)
    except Exception:
        raise HTTPException(503, "authorization read unavailable") from None
    supplied = hashlib.sha256(parts[1].encode()).hexdigest()
    principal_id = None
    for digest, identifier in bindings.items():
        if hmac.compare_digest(supplied, digest):
            principal_id = identifier
    if principal_id is None:
        raise HTTPException(403, "case read access denied")
    enabled, grants = principals[principal_id]
    if not enabled:
        raise HTTPException(403, "case read access denied")
    if case_id not in grants:
        raise HTTPException(404 if mask_ungranted else 403, "case read access denied")
    allowed = policy.allowed_documents[principal_id] if isinstance(policy, _NormalizedLifecyclePolicy) else None
    if isinstance(policy, _NormalizedLifecyclePolicy):
        retained = policy.retained_by_principal[principal_id]
    return AuthorizedCase(principal_id, case_id, retained, allowed)


def authorize_document(access, documents, case_id, document_id):
    """Trust exact committed metadata or retained owner-attested tuple on row loss."""
    validate_identifier(case_id)
    validate_identifier(document_id)
    if type(access) is not AuthorizedCase or access.case_id != case_id:
        raise HTTPException(403, "case read access denied")
    if access.allowed_documents is not None and (case_id, document_id) not in access.allowed_documents:
        raise HTTPException(404, "document not found")
    try:
        response = documents.get_item(Key={"case_id": case_id, "document_id": document_id}, ConsistentRead=True)
        if not isinstance(response, dict):
            raise ValueError("invalid membership response")
        item = response.get("Item")
        if item is not None and not isinstance(item, dict):
            raise ValueError("invalid membership row")
    except Exception:
        raise HTTPException(503, "membership read unavailable") from None
    if item is not None:
        member = item.get("case_id") == case_id and item.get("document_id") == document_id
    else:
        member = (case_id, document_id) in access.retained_documents
    if not member:
        raise HTTPException(404, "document not found")
    return AuthorizedDocumentScope(case_id, document_id)


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value) is not None and value not in {".", ".."}


def _policy(raw):
    policy = json.loads(raw)
    if (not isinstance(policy, dict) or set(policy) != {"schema_version", "credentials"}
            or type(policy["schema_version"]) is not int or policy["schema_version"] != 1
            or not isinstance(policy["credentials"], list) or not policy["credentials"]):
        raise ValueError("invalid monitoring policy")
    ids, digests = set(), set()
    for credential in policy["credentials"]:
        if (not isinstance(credential, dict) or set(credential) != {
                "credential_id", "sha256", "state", "principal_type", "principal_id", "grants"}
                or not _identifier(credential["credential_id"]) or not _identifier(credential["principal_id"])
                or credential["principal_type"] != "SERVICE" or credential["state"] not in {"active", "revoked"}
                or not isinstance(credential["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", credential["sha256"])
                or credential["credential_id"] in ids or credential["sha256"] in digests
                or not isinstance(credential["grants"], list)):
            raise ValueError("invalid monitoring credential")
        ids.add(credential["credential_id"])
        digests.add(credential["sha256"])
        cases = set()
        for grant in credential["grants"]:
            if (not isinstance(grant, dict) or set(grant) != {"case_id", "documents"}
                    or not _identifier(grant["case_id"]) or grant["case_id"] in cases
                    or not isinstance(grant["documents"], list)):
                raise ValueError("invalid case grant")
            cases.add(grant["case_id"])
            documents = set()
            for scope in grant["documents"]:
                if (not isinstance(scope, dict) or scope.get("membership") not in {"current", "retained"}
                        or not _identifier(scope.get("document_id")) or scope["document_id"] in documents):
                    raise ValueError("invalid document grant")
                documents.add(scope["document_id"])
                fields = {"document_id", "membership"}
                if scope["membership"] == "retained":
                    fields.add("provenance")
                    provenance = scope.get("provenance")
                    if (not isinstance(provenance, dict) or set(provenance) != {"record_id", "verified_by", "verified_at"}
                            or not _identifier(provenance["record_id"]) or not _identifier(provenance["verified_by"])):
                        raise ValueError("invalid retained provenance")
                    from datetime import datetime, timedelta
                    timestamp = datetime.fromisoformat(provenance["verified_at"].replace("Z", "+00:00"))
                    if timestamp.utcoffset() != timedelta(0):
                        raise ValueError("invalid retained verification time")
                if set(scope) != fields:
                    raise ValueError("invalid document grant fields")
    return policy


class ServiceDocumentAuthorizer:
    def __init__(self, secrets, secret_arn, documents):
        self.secrets, self.secret_arn, self.documents = secrets, secret_arn, documents

    def __call__(self, request, case_id, document_id):
        access = getattr(request.state, "processing_monitor_access", None)
        if access is None:
            source = getattr(request.app.state, "processing_monitor_authorization_source", None)
            if source is None:
                source = AuthorizationSecretSource(self.secret_arn, self.secrets)
            access = authorize_case(source,
                                    request.headers.get("authorization"), case_id, mask_ungranted=True)
        return authorize_document(access, self.documents, case_id, document_id)


def _normalize_lifecycle_policy(policy):
    """Validate historical schema, then use the same binding/grant implementation.

    Historical document-scoped grants must never expand to the whole case.
    The normalized access records carry an explicit document allowlist.
    """
    _policy(json.dumps(policy))
    normalized = {"version": 1, "credentials": [], "principals": [], "retained_documents": []}
    allowed = {}
    retained_by_principal = {}
    retained = {}
    for credential in policy["credentials"]:
        # Keep per-credential grants isolated during compatibility migration.
        principal = credential["credential_id"]
        normalized["credentials"].append({"sha256": credential["sha256"], "principal_id": principal})
        normalized["principals"].append({"id": principal, "type": "SERVICE",
            "enabled": credential["state"] == "active", "case_ids": [g["case_id"] for g in credential["grants"]]})
        allowed[principal] = frozenset((grant["case_id"], scope["document_id"])
            for grant in credential["grants"] for scope in grant["documents"])
        retained_by_principal[principal] = frozenset((grant["case_id"], scope["document_id"])
            for grant in credential["grants"] for scope in grant["documents"] if scope["membership"] == "retained")
        for grant in credential["grants"]:
            for scope in grant["documents"]:
                if scope["membership"] == "retained":
                    proof = scope["provenance"]
                    retained[(grant["case_id"], scope["document_id"])] = {
                        "case_id": grant["case_id"], "document_id": scope["document_id"],
                        "source_revision": proof["record_id"], "verified_at": proof["verified_at"]}
    normalized["retained_documents"] = list(retained.values())
    return _NormalizedLifecyclePolicy(normalized, allowed, retained_by_principal)


class _NormalizedLifecyclePolicy(dict):
    def __init__(self, policy, allowed, retained_by_principal):
        super().__init__(policy)
        self.allowed_documents = allowed
        self.retained_by_principal = retained_by_principal
