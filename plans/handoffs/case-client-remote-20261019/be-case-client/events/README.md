# be-case-client/events

Ukázkové události API Gateway (proxy) pro čtyři operace case-client Lambdy: `list-clients`, `create-case`, `get-case`, `list-client-cases`. Používají je testy a lokální vyvolání (`sam local invoke --event events/<soubor>.json`).

`create-case.json` posílá jen `client_id` a `metadata`; `case_id` generuje služba.
