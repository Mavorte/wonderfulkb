# Read-only concurrency audit — user1561985837728796672

No scheduler/lifecycle/source mutations by this audit. Live public task/batch enumeration and ps verification recorded in concurrency-audit-0814.json.

Observed8active monitor queues,7registry phase implementing/planning with already-exited PID and1live process (terminal2264932c) at observation. Process completed/output != settled accepted. No PID-based intervention. Logs show AttemptStarted and reducer report local tests; extraction/validation/page event attempts explicitly incomplete. Monitor owns reconciliation, not host speculative retries.

Previous operator statement of five independent EVENT lanes was incorrect. The actual canonical plans for08/10/12/16/22 all own audit_events.py and audit_storage.py, several audit_queries.py/listener too. They are NOT disjoint sources. Parallel split increased shared-source collision and unstable full-suite collection risk; current symptoms do not alone prove causality. Earliest dependency audit already said core events need one sequential writer. At-least-five was misapplied as five event writers PLUS three helpers, yielding8active. This is operator scheduling error, not justification to invent execution interface or waive tests.

Recommended FIVE lanes, sequential tasks within each:
1 audit/event contracts08→10→12→14→16→18→20→22; one owner of shared event/store/query modules at a time.
2 pure page mapper97212f63, own module/tests.
3 pure lifecycle reducer422c4f83, own module/tests.
4 runtime/context535479cc, actual confirmed identity seam or precise blocker; no fabricated execution semantics.
5 shared HTTP/OpenAPI continuation, actual existing03/06/circuit blockers preserved, then applicable reads/deploy/integration; independent source input gates must be enforced before release. Worker hooks/final proof need runtime+event+HTTP success, not just same queue placeholder.

Five logical queues != five perpetually runnable independent implementations. Current API base failure and missing runtime identity preclude honest guaranteed five simultaneous productive workers. Do not manufacture filler tasks or clear failed gates to meet concurrency count. Existing attempts/artifacts preserved; any authorized regroup should inspect live attempt/settlement before public batch moves. This audit proposes regroup only, no stop/move/reset performed. No new coding bug task: new finding is operator-owned scheduling, and product failures already have owning tasks; root-cause source repair not established here.
