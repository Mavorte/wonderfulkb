"""boto3 handles are created at call time so tests can run under moto."""
import boto3


class Aws:
    def __init__(self, settings):
        self.settings = settings
        self.s3 = boto3.client("s3", region_name=settings.region)
        ddb = boto3.resource("dynamodb", region_name=settings.region)
        self.documents = ddb.Table(settings.documents_table)
        self.analysis = ddb.Table(settings.analysis_table)

    def get_bytes(self, key):
        return self.s3.get_object(Bucket=self.settings.bucket, Key=key)["Body"].read()

    def get_bytes_or_none(self, key):
        try:
            return self.get_bytes(key)
        except self.s3.exceptions.NoSuchKey:
            return None

    def put_bytes(self, key, body, content_type, metadata=None, tagging=None):
        extra = {k: v for k, v in (("Metadata", metadata), ("Tagging", tagging)) if v}
        self.s3.put_object(Bucket=self.settings.bucket, Key=key, Body=body, ContentType=content_type, **extra)

    def head_metadata(self, key):
        """User metadata of an object, None when it does not exist."""
        try:
            return self.s3.head_object(Bucket=self.settings.bucket, Key=key)["Metadata"]
        except self.s3.exceptions.ClientError as error:
            if error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def list_documents(self, case_id):
        from boto3.dynamodb.conditions import Key
        items, kwargs = [], {"KeyConditionExpression": Key("case_id").eq(case_id)}
        while True:
            page = self.documents.query(**kwargs)
            items += page["Items"]
            if "LastEvaluatedKey" not in page:
                return sorted(items, key=lambda i: (i.get("filename", ""), i["document_id"]))
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
