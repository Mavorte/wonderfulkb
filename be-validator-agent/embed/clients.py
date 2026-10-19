"""Klienti AWS, retry s backoffem a omezení počtu volání Bedrocku."""
from __future__ import annotations

import collections
import os
import random
import threading
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

REGION = "eu-central-1"
VECTOR_BUCKET = "wonderfulkb-vectors"

# Bedrock má limit 50 požadavků/min na celý tým; tento proces si bere výchozích 30.
BEDROCK_RPM = int(os.environ.get("WONDERFULKB_BEDROCK_RPM", "30"))

RETRYABLE_CODES = {
    "ThrottlingException", "TooManyRequestsException", "ServiceUnavailableException",
    "InternalServerException", "ModelTimeoutException", "ModelNotReadyException",
    "ServiceQuotaExceededException", "RequestTimeout", "RequestTimeoutException",
    "SlowDown", "InternalFailure", "ServiceUnavailable", "ThrottledException",
}

_sess: boto3.Session | None = None
_clients: dict[str, object] = {}


def _session() -> boto3.Session:
    global _sess
    if _sess is None:
        _sess = boto3.Session(profile_name=os.environ.get("WONDERFULKB_AWS_PROFILE") or None,
                              region_name=REGION)
    return _sess


def _client(name: str):
    if name not in _clients:
        # opakování řešíme sami (call_with_retry), botocore ať nezdvojuje
        cfg = Config(retries={"max_attempts": 1, "mode": "standard"},
                     read_timeout=60, connect_timeout=10)
        _clients[name] = _session().client(name, config=cfg)
    return _clients[name]


def bedrock_client():
    return _client("bedrock-runtime")


def s3vectors_client():
    return _client("s3vectors")


class RateLimiter:
    """Posuvné okno: nejvýše `limit` volání za `window` sekund (sdílí všechna volání v procesu)."""

    def __init__(self, limit: int = BEDROCK_RPM, window: float = 60.0,
                 clock=time.monotonic, sleep=time.sleep):
        self.limit, self.window, self._clock, self._sleep = limit, window, clock, sleep
        self._calls: collections.deque[float] = collections.deque()
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self.limit <= 0:
            return
        while True:
            with self._lock:
                now = self._clock()
                while self._calls and now - self._calls[0] >= self.window:
                    self._calls.popleft()
                if len(self._calls) < self.limit:
                    self._calls.append(now)
                    return
                delay = self.window - (now - self._calls[0])
            self._sleep(max(delay, 0.01))


bedrock_limiter = RateLimiter()


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code", "")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return code in RETRYABLE_CODES or status in (429, 500, 502, 503, 504)
    return isinstance(exc, BotoCoreError)  # spojení, timeouty


def call_with_retry(fn, *, attempts: int = 6, base: float = 1.0, cap: float = 30.0,
                    sleep=None, limiter: RateLimiter | None = None):
    """Zavolá `fn()`; na throttling a přechodné chyby čeká s exponenciálním backoffem a jitterem."""
    sleep = sleep or time.sleep
    for attempt in range(attempts):
        if limiter is not None:
            limiter.wait()
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts - 1 or not is_retryable(exc):
                raise
            sleep(random.uniform(0, min(cap, base * 2 ** attempt)))
