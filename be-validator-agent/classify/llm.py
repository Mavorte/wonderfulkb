"""Volání modelu pro klasifikaci dokumentu: Bedrock Converse nebo Mantle, omezení rychlosti, retry, parsování JSON."""
import json
import logging
import os
import random
import threading
import time
import urllib.error
import urllib.request

from .prompt import LABEL_OUTPUT_SCHEMA, build_label_prompt_section

log = logging.getLogger(__name__)

REGION = "eu-central-1"
# EU inference profil (Haiku 4.5 nemá ve Frankfurtu přímou inferenci a profil může směrovat i do jiných EU regionů,
# viz README). Modely 5.5 se podle pravidel týmu nepoužívají.
DEFAULT_MODEL_ID = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
MANTLE_MODEL_ID = "qwen.qwen3-vl-235b-a22b-instruct"
RETRYABLE = {
    "ThrottlingException", "TooManyRequestsException", "ServiceUnavailableException",
    "ModelTimeoutException", "ModelNotReadyException", "InternalServerException",
}
HEAD_CHARS = 5000
TAIL_CHARS = 1500

SYSTEM_PROMPT = "Jsi klasifikátor dokumentů. Odpovídáš jen požadovanou strukturou, bez dalšího textu."


def build_user_prompt(text: str, page_count: int, taxonomy: dict) -> str:
    return (f"{build_label_prompt_section(taxonomy)}\n\nPočet stran: {page_count}\n\n"
            f"<dokument>\n{excerpt(text)}\n</dokument>")


def excerpt(text: str) -> str:
    """Začátek a konec textu: hlavička určuje typ nejvíc, podpisová část pomáhá u dlouhých dokumentů."""
    if len(text) <= HEAD_CHARS + TAIL_CHARS:
        return text
    return text[:HEAD_CHARS] + "\n[... vynecháno ...]\n" + text[-TAIL_CHARS:]


def tool_config() -> dict:
    return {
        "tools": [{"toolSpec": {
            "name": "classify",
            "description": "Vrátí typ dokumentu, popis a jistotu klasifikace.",
            "inputSchema": {"json": LABEL_OUTPUT_SCHEMA},
        }}],
        "toolChoice": {"tool": {"name": "classify"}},
    }


class RateLimiter:
    """Odstup mezi voláními v rámci procesu (tým sdílí 50 požadavků/min; výchozí strop je nižší)."""

    def __init__(self, per_minute: float, clock=time.monotonic, sleep=time.sleep):
        self.interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._clock, self._sleep = clock, sleep
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = self._clock()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if delay:
            self._sleep(delay)


class TransientError(Exception):
    """Přechodná chyba jiného zdroje než botocore (např. HTTP 429/5xx z Mantle); call_with_retry ji zopakuje."""


def _error_code(exc: Exception) -> str | None:
    return getattr(exc, "response", {}).get("Error", {}).get("Code")


def call_with_retry(fn, *, attempts=6, base=2.0, cap=30.0, sleep=time.sleep, rand=random.random):
    """Zavolá fn(); u omezení rychlosti a přechodných chyb čeká exponenciálně s jitterem."""
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # botocore ClientError, síťové chyby, TransientError
            transient = (isinstance(exc, TransientError) or _error_code(exc) in RETRYABLE
                         or type(exc).__name__ in ("ConnectTimeoutError", "ReadTimeoutError",
                                                   "EndpointConnectionError", "ConnectionClosedError"))
            if not transient or attempt == attempts - 1:
                raise
            delay = min(cap, base * 2 ** attempt) * (0.5 + rand() / 2)
            log.warning("Model %s, pokus %d/%d, čekám %.1f s", _error_code(exc) or type(exc).__name__,
                        attempt + 1, attempts, delay)
            sleep(delay)


def parse_json_text(text: str) -> dict:
    """Vytáhne JSON objekt z textu odpovědi (i když je v ``` bloku nebo má okolní text)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model nevrátil JSON")
    return json.loads(text[start:end + 1])


def parse_converse_response(resp: dict) -> dict:
    """Odpověď Converse: toolUse, jinak JSON v textu."""
    blocks = resp["output"]["message"]["content"]
    for b in blocks:
        if "toolUse" in b:
            return b["toolUse"]["input"]
    return parse_json_text("".join(b.get("text", "") for b in blocks))


def make_client(region: str = REGION):
    import boto3
    from botocore.config import Config
    # retry řešíme sami (viz call_with_retry), proto jen jeden pokus na úrovni botocore
    return boto3.client(
        "bedrock-runtime", region_name=region,
        config=Config(retries={"max_attempts": 1}, read_timeout=60, connect_timeout=10),
    )


class ConverseBackend:
    """Bedrock Converse (např. Haiku 4.5 přes EU inference profil); odpověď vynucená nástrojem `classify`."""

    name = "converse"

    def __init__(self, client=None, model_id: str = DEFAULT_MODEL_ID):
        self._client = client
        self.model_id = model_id

    @property
    def client(self):
        if self._client is None:
            self._client = make_client()
        return self._client

    def complete(self, user_prompt: str) -> tuple[dict, dict]:
        resp = self.client.converse(
            modelId=self.model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            inferenceConfig={"maxTokens": 400, "temperature": 0},
            toolConfig=tool_config(),
        )
        return parse_converse_response(resp), resp.get("usage", {})


class MantleBackend:
    """Bedrock Mantle (OpenAI chat/completions podepsané SigV4), např. Qwen3 VL; JSON se žádá v promptu."""

    name = "mantle"

    def __init__(self, model_id: str = MANTLE_MODEL_ID, region: str = REGION, session=None, opener=None):
        self.model_id, self.region = model_id, region
        self._session = session
        self._open = opener or urllib.request.urlopen

    @property
    def session(self):
        if self._session is None:
            import boto3
            self._session = boto3.Session()
        return self._session

    def complete(self, user_prompt: str) -> tuple[dict, dict]:
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest

        url = f"https://bedrock-mantle.{self.region}.api.aws/v1/chat/completions"
        system = SYSTEM_PROMPT + " Vrať pouze JSON objekt s poli label, description a confidence."
        payload = json.dumps({
            "model": self.model_id, "temperature": 0, "max_tokens": 600,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
        }, ensure_ascii=False, separators=(",", ":")).encode()
        creds = self.session.get_credentials()
        if creds is None:
            raise RuntimeError("chybí AWS přihlášení")
        signed = AWSRequest(method="POST", url=url, data=payload, headers={"Content-Type": "application/json"})
        SigV4Auth(creds.get_frozen_credentials(), "bedrock-mantle", self.region).add_auth(signed)
        req = urllib.request.Request(url, data=payload, headers=dict(signed.headers), method="POST")
        try:
            with self._open(req, timeout=75) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                raise TransientError(f"HTTP {e.code}") from e
            raise RuntimeError(f"Mantle HTTP {e.code}: {e.read()[:300]!r}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise TransientError(str(e)) from e
        choice = body["choices"][0]
        if choice.get("finish_reason") not in ("stop", None):
            raise ValueError(f"neúplná odpověď modelu ({choice.get('finish_reason')})")
        content = choice["message"]["content"]
        usage = body.get("usage", {})
        return parse_json_text(content), {"totalTokens": usage.get("total_tokens", 0)}


def make_backend(client=None, model_id: str | None = None, backend: str | None = None):
    """Výběr podle CLASSIFY_BACKEND (converse | mantle) a CLASSIFY_MODEL_ID; klient předaný zvenku = converse."""
    kind = backend or ("converse" if client is not None else os.environ.get("CLASSIFY_BACKEND", "converse"))
    if kind == "mantle":
        return MantleBackend(model_id or os.environ.get("CLASSIFY_MODEL_ID", MANTLE_MODEL_ID))
    if kind == "converse":
        return ConverseBackend(client, model_id or os.environ.get("CLASSIFY_MODEL_ID", DEFAULT_MODEL_ID))
    raise ValueError(f"neznámý backend {kind!r}")


def classify_with_model(backend, taxonomy: dict, text: str, page_count: int, *,
                        limiter: RateLimiter | None = None, sleep=time.sleep) -> tuple[dict, dict]:
    """Jedno volání modelu (s retry). Vrací (surový výsledek, usage). Název souboru se do promptu nedává."""
    prompt = build_user_prompt(text, page_count, taxonomy)

    def call():
        if limiter:
            limiter.wait()
        return backend.complete(prompt)

    return call_with_retry(call, sleep=sleep)


def default_limiter() -> RateLimiter:
    return RateLimiter(float(os.environ.get("CLASSIFY_MAX_RPM", "30")))
