"""Tells Wonderful that the documents of a case are processed, so its agent starts the evaluation.

The URL (it carries the webhook id) and the X-Webhook-Secret are in one Secrets Manager secret, JSON
{"url": ..., "secret": ...}, named by WONDERFUL_WEBHOOK_SECRET. Neither is in the code or the template:
the repository is public. An empty name turns the call off."""
import json
import logging
import os
import urllib.error
import urllib.request

import boto3

log = logging.getLogger("trigger.webhook")
TIMEOUT_SECONDS = 10
_config = None


class WebhookError(RuntimeError):
    pass


def enabled():
    return bool(os.environ.get("WONDERFUL_WEBHOOK_SECRET"))


def _load():
    global _config
    if _config is None:
        raw = boto3.client("secretsmanager").get_secret_value(SecretId=os.environ["WONDERFUL_WEBHOOK_SECRET"])
        value = json.loads(raw["SecretString"])
        if not (isinstance(value, dict) and str(value.get("url", "")).startswith("https://") and value.get("secret")):
            raise WebhookError("webhook secret must be JSON with an https url and a secret")
        _config = value
    return _config


def start_evaluation(case_id):
    """POST {"payload": {"case_id": ...}}. Raises WebhookError on anything but 2xx (the message is retried)."""
    config = _load()
    request = urllib.request.Request(
        config["url"], method="POST", data=json.dumps({"payload": {"case_id": case_id}}).encode(),
        headers={"Content-Type": "application/json", "X-Webhook-Secret": config["secret"]})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 - https only, checked in _load
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    except OSError as error:
        raise WebhookError(f"webhook unreachable: {type(error).__name__}") from None
    if not 200 <= status < 300:
        raise WebhookError(f"webhook answered {status}")
    log.info("case %s: evaluation webhook accepted (%s)", case_id, status)
    return status
