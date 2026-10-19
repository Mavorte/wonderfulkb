"""AWS Lambda adaptér (API Gateway REST proxy, payload 1.0, i HTTP API 2.0). Handler: app.handler"""
import base64

import core


def handler(event, context=None):
    rc = event.get("requestContext", {})
    http = rc.get("http", {})
    method = http.get("method") or event.get("httpMethod", "GET")
    path = event.get("rawPath") or event.get("path", "/")
    q = event.get("multiValueQueryStringParameters") or event.get("queryStringParameters") or {}
    request = {"request_id": rc.get("requestId") or getattr(context, "aws_request_id", None),
               "api_key_id": (rc.get("identity") or {}).get("apiKeyId")}  # jen REST API s usage plan; HTTP API ne
    status, body = core.handle(method, path, q, event.get("headers") or {}, request=request)
    if isinstance(body, core.Binary):  # odkrytý výřez: binární tělo, nikdy v mezipaměti
        return {"statusCode": status, "isBase64Encoded": True,
                "headers": {"Content-Type": body.content_type, **body.headers},
                "body": base64.b64encode(body.data).decode("ascii")}
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"},
            "body": core.dumps(body).decode("utf-8")}
