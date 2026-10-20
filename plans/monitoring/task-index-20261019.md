# Monitoring — registrované tasky

Batch: `wonderfulkb-document-monitoring-20261019` — inactive; všech 18 členů backlog, default-paused, bez runtime. Parametry schválené 19. 10. 2026 ve 20:30, proposal `proposal-20261019-150954-c8891f`.

1. **Monitoring: doložit producenty, ingest routing a autorizační hranici** — `task-5644e4cd-a516-4bf1-8e6d-0b0e8bf85dbf` (`source-contract`), [brief](../tasks/2026-10-19_monitoring-01-producer-contract.md)
2. **Monitoring: prokázat bounded cursor a refresh opožděných událostí** — `task-ab05414b-4a7f-43bf-bf4e-d222289e21f6` (`data-model`), [brief](../tasks/2026-10-19_monitoring-02-late-event-cursor.md)
3. **Monitoring: sjednotit read-only upload a analysis pohled** — `task-f793d823-ac5f-4dcf-ae5e-e695e1e4e385` (`read-api`), [brief](../tasks/2026-10-19_monitoring-03-business-read.md)
4. **Monitoring: zpřístupnit bezpečný list a detail přes backoffice proxy** — `task-b4546471-593e-4a01-af1c-dc832e96620a` (`read-api`), [brief](../tasks/2026-10-19_monitoring-04-business-api-auth.md)
5. **Monitoring: zobrazit současné dokumenty a poctivý legacy detail** — `task-bcbf162a-9ab2-456d-95a2-cf304c9be214` (`monitor-ui`), [brief](../tasks/2026-10-19_monitoring-05-legacy-ui.md)
6. **Monitoring: zavést immutable Event a fail-open auditní rozhraní** — `task-60d64a4a-59de-4cbe-9255-c5870b2ad50c` (`signals`), [brief](../tasks/2026-10-19_monitoring-06-audit-boundary.md)
7. **Monitoring: uložit idempotentní event deník s bounded dotazy** — `task-a26bcfeb-5f89-488c-818b-f94b232ecc42` (`data-model`), [brief](../tasks/2026-10-19_monitoring-07-audit-persistence.md)
8. **Monitoring: emitovat FileReceived na potvrzeném ingest commitu** — `task-0a648288-6108-458d-92bf-876c952d7984` (`instrumentation`), [brief](../tasks/2026-10-19_monitoring-08-file-received.md)
9. **Monitoring: zachytit skutečné enqueue a začátek pokusu** — `task-a56e7c1c-d95b-40eb-bd64-8c6acc73b496` (`instrumentation`), [brief](../tasks/2026-10-19_monitoring-09-queue-attempt.md)
10. **Monitoring: zachytit ověření vstupu a skutečné cache reuse** — `task-851183f5-ce74-4e7e-b68d-f639beb5af16` (`instrumentation`), [brief](../tasks/2026-10-19_monitoring-10-source-cache.md)
11. **Monitoring: zaznamenat stránkové outcome bez duplicitních terminálů** — `task-0695baf6-ddac-42c6-a1b2-bc8157665682` (`instrumentation`), [brief](../tasks/2026-10-19_monitoring-11-page-outcomes.md)
12. **Monitoring: zachytit extraction a skutečný signature outcome** — `task-f9dc3497-c9be-4b2c-8568-57b241617f91` (`instrumentation`), [brief](../tasks/2026-10-19_monitoring-12-extraction-signatures.md)
13. **Monitoring: doložit publish, retry a terminály runů a pokusů** — `task-d1a5fc60-6c51-4e90-846f-4668f0ad0390` (`instrumentation`), [brief](../tasks/2026-10-19_monitoring-13-publish-terminal.md)
14. **Monitoring: číst audit, runy a timeline ze stejného deníku** — `task-a1ea312b-c20a-4408-bcd8-1b24d83bf337` (`read-api`), [brief](../tasks/2026-10-19_monitoring-14-history-api.md)
15. **Monitoring: bezpečně zpřístupnit jen doložené artefakty a jejich verze** — `task-f59b6b34-2a3a-4b93-8e67-5012d8fc1d17` (`read-api`), [brief](../tasks/2026-10-19_monitoring-15-artifact-api.md)
16. **Monitoring: zobrazit run timeline s řízeným pollingem** — `task-e8e86b26-11a2-465a-b0c3-5138a0b089a3` (`monitor-ui`), [brief](../tasks/2026-10-19_monitoring-16-timeline-ui.md)
17. **Monitoring: zobrazit stránky, historické výstupy a bezpečnou diagnostiku** — `task-9bb6deb7-9e59-43e9-9278-c06543175b43` (`monitor-ui`), [brief](../tasks/2026-10-19_monitoring-17-pages-ui.md)
18. **Monitoring: prokázat celý syntetický tok a fail-open ekvivalenci** — `task-85f8de28-81e8-4e8c-a4f4-bb608cc2fd72` (`delivery`), [brief](../tasks/2026-10-19_monitoring-18-synthetic-e2e.md)

Technické prerequisite a budoucí host readiness: [operator checkpoint](operator-checkpoint-20261019.md). YAML/lokální reference a dokumenty ověřeny, nikoli implementace nebo živé AWS.
