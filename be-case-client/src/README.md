# be-case-client/src

Kód Lambdy bez externích závislostí (jen standardní knihovna Pythonu).

| Soubor | Účel |
|---|---|
| `case_client_handler.py` | Handler API Gateway: routování, validace vstupu, převod chyb na HTTP kódy. |
| `case_client_repository.py` | Rozhraní perzistence (čtyři operace) a výjimky `InvalidRequest`, `NotFound`, `Conflict`. |
| `case_client_mock_repository.py` | Syntetická in-memory data (jen pro běh instance), generuje `case_id` (UUID v4). |
| `case_client_fixtures.json` | Syntetičtí klienti a case pro mock. |
