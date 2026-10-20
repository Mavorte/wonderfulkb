# Read-only live trigger evidence — 2026-10-19

Podklad pro sekce RunQueued/AttemptStarted. Žádný kód nebyl spuštěn, změněn nebo nasazen; žádné queue/business writes, dokumenty ani credentials nebyly čteny. Read-only AWS profile ai-hackathon, eu-central-1; API metadata a source artefakty pouze.

## Pozorované hranice
- Enqueue ZIP: wonderfulkb-trigger-enqueue, trigger.enqueue_handler.handler. Stream INSERT volá common.enqueue_document. common.py make_message: JSON v/type/case_id/document_id a volitelný force; **žádný run_id ani job_id**. common.Context.send volá SQS SendMessage, response nevrací. enqueue_document zapisuje queued business analysis a potom send, vrací queued. Opakované messages jsou dovolené.
- Worker image: wonderfulkb-trigger-worker, digest sha256:8603c8389fd1aab9a073cc996ed34d346fcc877270b5ba190d265826d4a45591, revision 418be116-00f0-42bb-a434-086fbadad787. CloudFormation ImageConfig command trigger.worker_handler.handler. Ověřený layer sha256:ac960253032b9d447f652b7130d67053e4d73a2c429d99fb64074f7de4b03f6f obsahuje var/task/trigger/common.py a worker_handler.py. common.py je byte-for-byte shodný s enqueue ZIP.
- claim_document: conditional queued nebo expired processing → processing; timestamp updated_at slouží lease. **Žádný stored run_id, owner token ani inkrement attempt counter v tomto claimu.** process_document po claimed spouští pipeline.run_document; handle_record mu předá parsovaný message bez SQS receive count. ApproximateReceiveCount je pouze v error logu handleru, není autoritativní attempt_no.
- Žádná vazba na checked-in be-document-processing Pipeline.process(job_id). Ten má jiný job/run/attempt model, není prokázaný živý owner.

## Source provenance a omezení
Repo local search nenalezl trigger/common.py ani worker_handler.py; GitHub main tree Mavorte/wonderfulkb read-only prohlédnut (689 paths), trigger source nenalezen. To nedokazuje nepřítomnost v jiných refs/repos ani autora zdroje. Stack wonderfulkb-trigger nemá metadata owner/source revision; tags component=trigger, project=wonderfulkb. Samotný nasazený artefakt není oprávněním deklarovat canonical repo nebo jej automaticky importovat.

## Výsledek pro zadání
RunQueued producer a AttemptStarted producer **nejsou ready implementační zadání**. Nejdřív stanovit canonical source owner a autoritativní run/attempt kontrakt. Neměnit business tabulky, payload queue, retry/lease nebo vytvářet fake run identity kvůli auditu. Stejně tak nelze slíbit skutečný E2E těchto událostí. Lze samostatně připravit event/read kontrakt a hermeticky doložit jeho chování, jasně ne jako producer/live důkaz.

## Ověřovací rozhraní
aws lambda get-function (jen source artefakt/provenance), cloudformation get-template/describe-stacks, ecr batch-get-image/get-download-url-for-layer (jen malý source layer), gh api repos/Mavorte/wonderfulkb/git/trees/main?recursive=1. Presigned URL a plné AWS response nejsou workspace artefakty.

## SHA256 stažených zdrojů
- wkb-2302-enqueue-common.py: `dad3fb529dedc96235f263677728a4b8680d8e9e97726a3003d25e0570504d5e`
- wkb-2302-worker-common.py: `dad3fb529dedc96235f263677728a4b8680d8e9e97726a3003d25e0570504d5e`
- wkb-2302-worker-worker_handler.py: `c77a2c5e40df3ed242fb733d614c569539daa32ff33ebaf567411d4c5be4e75e`

## Superseding source verification — user23:17
Searching only checkout/main was insufficient. `trigger-source-search-20261019.md` finds canonical candidate modules in wonderfulkb branch refs feat-validator-agent-v2/fix-audit-findings, commit475deafc567366c2587ef4d73fbf9a31fadb59f8 under be-validator-agent/trigger. Host independently proved common.py and worker_handler.py byte-identical to deployed artifacts with hashes above. Source lookup is therefore resolved at exact-module equivalence, not full-image build provenance. Resource Metadata also reveals DockerContext infra/validator-agent/trigger/build/pkg on teammate build machine; top-level Metadata=None was not the whole metadata check.

The missing run/attempt semantics are confirmed in both repository and runtime code, not an investigation to defer to a coding agent. Authoritative run identity and durable claim-attempt ordinal require an explicit execution-owner change (queue context plus separate runtime state if business tables remain unchanged). Audit cannot allocate these from its best-effort events, use SQS receive count or silently change an execution contract. This decision remains pre-dispatch, not a markdown dependency in the batch.
