"""AWS Lambda adaptér (API Gateway REST proxy, payload 1.0, i HTTP API 2.0). Handler: app.handler

Jedna Lambda pro všechny endpointy: dokumenty, vektory a podpisy obsluhuje `core`, případy a klienty
(`/cases`, `/cases/{case_id}`, `/clients`, `/clients/{client_id}/cases`, dříve Lambda wonderfulkb-case-client)
obsluhuje `case_client_handler`, regiony (`/cases/{case_id}/regions`, `…/documents/{document_id}/regions`)
`regions_api`. Vše za stejnou kontrolou x-api-key.
"""
import base64
import re

import core
import regions_api

# Cesty Case & Client API; /cases/{case_id}/documents… zůstávají v core.
CASE_CLIENT_RX = re.compile(r"^/(?:cases|clients)(?:/[^/]+)?$|^/clients/[^/]+/cases$")


def _case_client(event, context, method, path, headers):
    denied = core.authorize(headers)
    if denied:
        status, body = denied
        return {"statusCode": status,
                "headers": {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"},
                "body": core.dumps(body).decode("utf-8")}
    import case_client_handler  # líně: simplejson a jeho konfigurace jen pro tyto cesty
    q = event.get("queryStringParameters")
    resp = case_client_handler.lambda_handler({
        "httpMethod": method.upper(), "resource": path, "path": path, "pathParameters": None,
        "queryStringParameters": q, "body": event.get("body"),
        "isBase64Encoded": event.get("isBase64Encoded", False)}, context)
    resp.setdefault("headers", {})["Cache-Control"] = "no-store"
    return resp


def handler(event, context=None):
    rc = event.get("requestContext", {})
    http = rc.get("http", {})
    method = http.get("method") or event.get("httpMethod", "GET")
    path = event.get("rawPath") or event.get("path", "/")
    q = event.get("multiValueQueryStringParameters") or event.get("queryStringParameters") or {}
    headers = event.get("headers") or {}
    if CASE_CLIENT_RX.match(core.strip_base(path)):
        return _case_client(event, context, method, core.strip_base(path), headers)
    if regions_api.matches(core.strip_base(path)):
        status, body = regions_api.handle(method, core.strip_base(path), q, headers)
        return {"statusCode": status,
                "headers": {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"},
                "body": core.dumps(body).decode("utf-8")}
    request = {"request_id": rc.get("requestId") or getattr(context, "aws_request_id", None),
               "api_key_id": (rc.get("identity") or {}).get("apiKeyId")}  # jen REST API s usage plan; HTTP API ne
    status, body = core.handle(method, path, q, headers, request=request)
    if isinstance(body, core.Binary):  # odkrytý výřez: binární tělo, nikdy v mezipaměti
        return {"statusCode": status, "isBase64Encoded": True,
                "headers": {"Content-Type": body.content_type, **body.headers},
                "body": base64.b64encode(body.data).decode("ascii")}
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store"},
            "body": core.dumps(body).decode("utf-8")}
