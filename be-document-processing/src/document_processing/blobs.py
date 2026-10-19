import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4


class LocalBlobs:
    def __init__(self, directory: Path):
        self.root = directory / "objects"
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        result = (self.root / key).resolve()
        if not result.is_relative_to(self.root.resolve()):
            raise ValueError("invalid object key")
        return result

    def put(self, key, body, content_type="application/json", immutable=True):
        destination = self.path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + "." + uuid4().hex)
        try:
            with temporary.open("xb") as stream:
                stream.write(body)
            if immutable:
                # Atomic no-overwrite publication, including concurrent uploads.
                os.link(temporary, destination)
            else:
                os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return {"version_id": "local-immutable", "size_bytes": len(body)}

    def head(self, key, version=None):
        return {"version_id": "local-immutable", "size_bytes": self.path(key).stat().st_size}

    def read(self, key, version=None):
        return self.path(key).read_bytes()

    def put_json(self, key, value):
        self.put(key, json.dumps(value, ensure_ascii=False).encode())

    def read_json(self, key):
        return json.loads(self.read(key))


class AwsBlobs:
    def __init__(self, settings, client=None):
        import boto3
        self.client = client or boto3.client("s3", region_name=settings.bedrock_region)
        self.bucket = settings.bucket

    def put(self, key, body, content_type="application/json", immutable=True):
        args = {"Bucket": self.bucket, "Key": key, "Body": body, "ContentType": content_type}
        if immutable:
            args["IfNoneMatch"] = "*"
        from botocore.exceptions import ClientError
        try:
            response = self.client.put_object(**args)
        except ClientError as error:
            if error.response["Error"]["Code"] in ("PreconditionFailed", "412", "ConditionalRequestConflict"):
                raise FileExistsError(key) from error
            raise
        return {"version_id": response.get("VersionId"), "size_bytes": len(body)}

    def head(self, key, version=None):
        args = {"Bucket": self.bucket, "Key": key}
        if version:
            args["VersionId"] = version
        from botocore.exceptions import ClientError
        try:
            result = self.client.head_object(**args)
        except ClientError as error:
            if error.response["Error"]["Code"] in ("NoSuchKey", "NoSuchVersion", "404", "NotFound"):
                raise FileNotFoundError(key) from error
            raise
        return {"version_id": result.get("VersionId"), "size_bytes": result["ContentLength"]}

    def read(self, key, version=None):
        args = {"Bucket": self.bucket, "Key": key}
        if version:
            args["VersionId"] = version
        from botocore.exceptions import ClientError
        try:
            return self.client.get_object(**args)["Body"].read()
        except ClientError as error:
            if error.response["Error"]["Code"] in ("NoSuchKey", "NoSuchVersion", "404", "NotFound"):
                raise FileNotFoundError(key) from error
            raise

    def put_json(self, key, value):
        self.put(key, json.dumps(value, ensure_ascii=False).encode())

    def read_json(self, key):
        return json.loads(self.read(key))

    def upload_url(self, key, content_type):
        return self.client.generate_presigned_url(
            "put_object", Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type}, ExpiresIn=900,
        )


def get_sha256(body):
    return hashlib.sha256(body).hexdigest()
