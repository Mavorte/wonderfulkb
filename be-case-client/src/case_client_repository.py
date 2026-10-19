"""The four-operation persistence boundary; no transport or AWS dependency."""
from typing import Protocol


class InvalidRequest(ValueError):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class CaseClientRepository(Protocol):
    def list_clients(self, filters: dict, limit: int, token: str = None) -> dict: ...

    def create_case(self, case_id: str, client_id: str, metadata: dict) -> tuple: ...

    def get_case(self, case_id: str) -> dict: ...

    def list_client_cases(self, client_id: str, filters: dict,
                          limit: int, token: str = None) -> dict: ...
