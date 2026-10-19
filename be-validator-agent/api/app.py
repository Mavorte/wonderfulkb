"""AWS Lambda adaptér (API Gateway REST proxy, payload 1.0, i HTTP API 2.0). Handler: app.handler"""
import base64

import core


def handler(event, context=None):
    http = event.get("requestContext", {}).get("http", {})
    method = http.get("method") or event.get("httpMethod", "GET")
    path = event.get("rawPath") or event.get("path", "/")
    q = event.get("multiValueQueryStringParameters") or event.get("queryStringParameters") or {}
    status, body = core.handle(method, path, q, event.get("headers") or {})
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"},
            "body": core.dumps(body).decode("utf-8")}
