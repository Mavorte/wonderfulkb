"""Volání modelu pro štítky regionů. Retry, omezovač rychlosti, klient a parsování převzaté z `classify.llm`
(sourozenecký modul v infra/validator-agent), tady jen obecné `complete_json(system, user, schema)`.

Výchozí je Bedrock Converse s Haiku 4.5 (EU profil, odpověď vynucená nástrojem se schématem), alternativa Mantle
s Qwen (bez týmového limitu, JSON z promptu): `REGIONS_BACKEND=converse|mantle`, `REGIONS_MODEL_ID`.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_PARENT = Path(__file__).resolve().parents[2]
if str(_PARENT) not in sys.path:
    sys.path.append(str(_PARENT))

from classify.llm import (  # noqa: E402
    DEFAULT_MODEL_ID, MANTLE_MODEL_ID, REGION, RateLimiter, TransientError, call_with_retry, make_client,
    parse_json_text,
)

MAX_TOKENS = 8000


class ConverseBackend:
    name = "converse"

    def __init__(self, client=None, model_id=DEFAULT_MODEL_ID):
        self._client, self.model_id = client, model_id
        self.usage = {"inputTokens": 0, "outputTokens": 0}

    @property
    def client(self):
        if self._client is None:
            self._client = make_client()
        return self._client

    def complete_json(self, system, user, schema, limiter=None):
        def call():
            if limiter:
                limiter.wait()
            return self.client.converse(
                modelId=self.model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0},
                toolConfig={"tools": [{"toolSpec": {"name": "label_regions", "description": "Štítky regionů dokumentu.",
                                                    "inputSchema": {"json": schema}}}],
                            "toolChoice": {"tool": {"name": "label_regions"}}},
            )

        resp = call_with_retry(call)
        for key in self.usage:
            self.usage[key] += resp.get("usage", {}).get(key, 0)
        if resp.get("stopReason") == "max_tokens":
            raise ValueError("odpověď modelu useknutá (max_tokens)")
        for block in resp["output"]["message"]["content"]:
            if "toolUse" in block:
                return block["toolUse"]["input"]
        return parse_json_text("".join(b.get("text", "") for b in resp["output"]["message"]["content"]))


class MantleBackend:
    name = "mantle"

    def __init__(self, model_id=MANTLE_MODEL_ID, region=REGION, session=None, opener=None):
        self.model_id, self.region = model_id, region
        self._session, self._open = session, opener or urllib.request.urlopen
        self.usage = {"totalTokens": 0}

    def complete_json(self, system, user, schema, limiter=None):
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest

        if self._session is None:
            import boto3
            self._session = boto3.Session()
        url = f"https://bedrock-mantle.{self.region}.api.aws/v1/chat/completions"
        prompt = f"{user}\n\nVrať pouze JSON objekt podle schématu:\n{json.dumps(schema, ensure_ascii=False)}"
        payload = json.dumps({"model": self.model_id, "temperature": 0, "max_tokens": MAX_TOKENS,
                              "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                             ensure_ascii=False).encode()

        def call():
            if limiter:
                limiter.wait()
            creds = self._session.get_credentials()
            if creds is None:
                raise RuntimeError("chybí AWS přihlášení")
            signed = AWSRequest(method="POST", url=url, data=payload, headers={"Content-Type": "application/json"})
            SigV4Auth(creds.get_frozen_credentials(), "bedrock-mantle", self.region).add_auth(signed)
            req = urllib.request.Request(url, data=payload, headers=dict(signed.headers), method="POST")
            try:
                with self._open(req, timeout=120) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    raise TransientError(f"HTTP {e.code}") from e
                raise RuntimeError(f"Mantle HTTP {e.code}: {e.read()[:300]!r}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                raise TransientError(str(e)) from e

        body = call_with_retry(call)
        self.usage["totalTokens"] += body.get("usage", {}).get("total_tokens", 0)
        choice = body["choices"][0]
        if choice.get("finish_reason") not in ("stop", None):
            raise ValueError(f"neúplná odpověď modelu ({choice.get('finish_reason')})")
        return parse_json_text(choice["message"]["content"])


def make_backend(kind=None, model_id=None):
    kind = kind or os.environ.get("REGIONS_BACKEND", "converse")
    model_id = model_id or os.environ.get("REGIONS_MODEL_ID")
    if kind == "mantle":
        return MantleBackend(model_id or MANTLE_MODEL_ID)
    if kind == "converse":
        return ConverseBackend(model_id=model_id or DEFAULT_MODEL_ID)
    raise ValueError(f"neznámý backend {kind!r}")


def default_limiter():
    """Tým sdílí 50 požadavků/min na Claude; výchozí strop je nižší (REGIONS_MAX_RPM)."""
    return RateLimiter(float(os.environ.get("REGIONS_MAX_RPM", "20")))
