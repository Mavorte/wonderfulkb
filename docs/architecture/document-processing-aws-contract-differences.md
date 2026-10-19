# Document Processing: rozdíly živého AWS a kontraktu komponenty

Podklad pro samostatné srovnání kontraktu komponenty s existujícími business daty. Nejde o návrh migrace dat, hotovou opravu ani pokyn k deployi. **Stávající business tabulky, hodnoty, identity a S3 objekty mají zůstat jak jsou; přizpůsobovat se má integrační vrstva komponenty.** Audit je vedlejší interní package stejné služby a není prostředkem k nápravě těchto nesouladů.

Souvislost: [proposal monitoringu a auditu](../proposals/proposal-20261019-150954-c8891f_monitoring-zpracovani-dokumentu-prubeh-mezivysledky-a-audit.md).

## Jak byl stav ověřen

Read-only AWS profil `ai-hackathon`, region `eu-central-1`, 19. 10. 2026. `DescribeTable` pro oba dokumentové zdroje a omezené `Scan --limit 10`: exportovány pouze klíčové definice a názvy/typy atributů, nikoli obsahy dokumentů, obchodní hodnoty či identity řádků. Náhled dokumentové tabulky byl při následné kontrole neúplný (LastEvaluatedKey přítomen), proto z něho nelze odvozovat její celkový počet nebo úplný seznam všech volitelných atributů. Analysis scan v této kontrole vyčerpal tabulku. Absence atributu ve vzorku neznamená zákaz atributu v DynamoDB.

Dřívější kontrola S3 pouze `ListObjectsV2` a `HeadObject` ověřila dostupnost/version metadata odkazovaných textových objektů. **Obsahy textů a výsledkových souborů se nestahovaly**; jejich fyzický formát není tímto ověřen. Živá data se v průběhu kontroly mění, historické počty nejsou kontrakt.

## 1. Primární klíče a serializace — přímo nekompatibilní

**Živá data:**
- `wonderfulkb-uw-documents`: partition `case_id` (S), sort `document_id` (S).
- `wonderfulkb-uw-document-analysis`: stejné klíče.
- Business atributy jsou samostatná DynamoDB pole, v obou ověřených tabulkách žádný GSI.

**Komponenta:**
- `AwsRepository` používá `pk` + `sk` a JSON serializovaný v `payload`, vedle `revision`.
- Dokument je pod `pk=CASE#<case_id>, sk=DOC#<document_id>`.
- Čtení očekává `json.loads(item['payload'])`; update dělá celý PutItem a optimistic condition nad `revision`.
- Její SAM vytváří právě tuto jinou pk/sk tabulku a předává ji přes `DOCUMENTS_TABLE_NAME`.

**Dopad:** změnit pouze konfiguraci `DOCUMENTS_TABLE_NAME` na existující tabulku nestačí. Get/Query/Put požadavky nemají její klíče; JSON obálka a revision tam navíc nejsou požadovaný kontrakt. Generický whole-item Put by po odstranění klíčového problému mohl zahodit pole jiného vlastníka.

**Směr nápravy:** explicitní read/business adapter pro existující klíče a flat atributy; žádné přejmenování klíčů nebo zabalení stávajících řádků do payload. Zachovat vlastnictví polí a při případném business zápisu neodstraňovat cizí atributy. Runtime jobs/korekce neukládat do živé business tabulky pod nesouvisejícími syntetickými klíči.

Zdroj: `be-document-processing/src/document_processing/repository.py:64–116`, `service.py:37–50`, `be-document-processing/template.yaml` (`DocumentsTable`, `Globals.Function.Environment`), `be-intake/documents-table/template.yaml`.

## 2. Metadata originálu — pole nejsou stejná

**Živá documents tabulka — pozorované názvy/typy:**
```text
case_id S, document_id S, filename S, content_type S, size_bytes N,
s3_key S, sha256 S, received_at S, uploaded_by S (volitelné)
```

**Komponenta:** očekává dokument s `schema_version`, `client_id`, `source_key`, `source_sha256`, `source_version`, `created_at`, `updated_at`, `mode`, `processing_status`, `job_id`, `run_id` a vlastními upload token/expiry metadaty. Pole se doplňují v různých fázích; nejde všechna o vstupní povinné atributy.

**Dopad:** `s3_key != source_key`, `sha256 != source_sha256`, `received_at` je čas přijetí, nikoli historie kroků. Existující originál nemá dokládaný job/run, režim OCR ani token nového uploadu. Není bezpečné doplnit vymyšlené hodnoty a prezentovat je jako uložené business údaje.

**Směr nápravy:** explicitně mapovat existující metadata při čtení; client odvodit z existujícího case, nikoli měnit upload řádek. Režim/config a source verzi určenou pro nový processing evidovat v odpovídajícím execution kontextu. Audit si jejich prokázané hodnoty referencuje vedle, nepřidává je zpětně do business tabulky. `uploaded_by` zachovat, nevymýšlet mu ekvivalent v neexistujícím worker actorovi.

Zdroj: `service.py:52–123`, `config.py:22–26,48–53`, `be-intake/app/main.py:203–219`.

## 3. Identita dokumentu a ingest workflow — není pouhé přejmenování polí

**Současný ingest zdroj:** `document_id = UUIDv5(DOC_NAMESPACE, case_id + ':' + sha256)`; stejný obsah v témže případu vrací existující ID a `duplicate=true`. Přijímá PDF multipart upload přes existující `be-intake`; business originál musí zachovat svoje již přidělené ID.

**Document Processing zdroj:** `create_upload` zakládá nové `UUIDv4` při každém vytvoření dokumentu, vytvoří awaiting_upload record, vrací PUT URL, potom očekává samostatné dokončení uploadu a založí vlastní job.

**Dopad:** jde o dva různé ingest kontrakty. Použít nový create_upload nad již přijatým dokumentem by vytvořilo jinou identitu a další upload, nikoli pouze zahájilo OCR. Rozdíl je ověřen ve zdrojích; nebylo provedeno živé POST/API replay.

**Směr nápravy:** processing má přijmout existující `(case_id, document_id)` a reference originálu. Neměnit historická ID ani opakovaně nahrávat business dokumenty kvůli auditu. Volba jediného ingest ownera a případné zachování samostatného dev uploadu musí být explicitní integrační rozhodnutí.

Zdroj: `be-intake/app/main.py:169–250`, `be-intake/openapi-ingest.yaml`, `be-document-processing/src/document_processing/service.py:52–69,80–123`.

## 4. S3 cesty a reference výstupu — nelze je sestavovat podle worker prefixu

**Existující ingest/analysis kontrakt:** ingest zapisuje do `cases/<case_id>/original/<document_id>.pdf`, živá documents tabulka ukazuje `s3_key`. Analysis má `text_s3_key`; její nasazený table template popisuje analýzu pod `cases/<case_id>/analysis/<document_id>/`. Referencované textové objekty byly metadata-read dostupné a verzované.

**Komponenta:**
- nové originály `originals/<case_id>/<document_id>`;
- previews `previews/<case_id>/<document_id>/<page>.png`;
- cache `cache/<job_id>/<config_hash>/<page>.json`;
- finální JSON `results/<case_id>/<document_id>/<run_id>/<owner>/result.json`, na nějž ukazuje její `result_key`.

**Dopad:** `text_s3_key` není prokázaný ekvivalent `result_key`: první odkazuje text dle analysis kontraktu, druhý strukturovaný `DocumentResult`. Přípony ani prefixy nejsou důkaz formátu, obsah nebyl stažen.

**Směr nápravy:** číst skutečné reference existujících business záznamů, nepřejmenovávat ani nepřesouvat objekty. Adapter musí znát typ obsahu a jeho kontrakt; audit pouze referencuje doloženou verzi/hash, pokud jsou známy. Vlastní auditní manifest do jiného auditního prefixu, ne do business struktury. Nevytvářet z plain textu domnělé OCR bloky a citace.

Zdroj: `be-intake/app/main.py:203–215`, `service.py:60,125–130`, `pipeline.py:58–81,119–125`, `blobs.py`.

## 5. Výsledek analýzy — dva odlišné modely

**Živá analysis tabulka — pozorované názvy/typy:**
```text
case_id S, document_id S, title S, description S,
label S, label_status S, confidence N, page_count N,
processing_status S, pipeline_version S, updated_at S, text_s3_key S
```

**Zdrojový DocumentResult:**
```text
schema_version, case_id, client_id, document_id, run_id,
source_sha256, page_count, processing_status,
ocr.pages[], extraction {document_type, fields[], warnings, model, prompt_version},
errors[], processing {...}, corrections[]
```
Výsledek je v S3 JSON, dokumentový runtime record drží result_key. Komponenta nemá v ověřeném Settings samostatné `analysis_table` a `get_result` nečte živou analysis tabulku.

**Dopad:** klasifikace/shrnutí nejsou totéž jako vytěžené field/evidence objekty. `label` se nedá bez schválené taxonomie prostě přejmenovat na `extraction.document_type`; `confidence` je podle validator kontraktu jistota klasifikace, nikoli OCR přesnost, completeness nebo kvalita všech fields. `label_status=verified` nelze odvozovat z completed OCR. Chybějící `ocr.pages`, run/evidence nejsou poctivě rekonstruovatelné z jednoho textového odkazu.

**Směr nápravy:** udržet současný business analysis kontrakt; stanovit read mapping a skutečné capability coverage. Nové bohatší výstupy generuje a publikuje dohodnutý processing owner, nikoli audit. Legacy view ukáže dostupný text/metadata a nedostupnou historii/field evidence, bez výroby fiktivních dat. Jakékoli nové business výstupy/formáty jsou samostatný scope.

Zdroj: `models.py:178–223`, `service.py:125–140`, `pipeline.py:109–125`, `config.py`, `VALIDATOR-AGENT.md` sekce Dokument.

## 6. Stavy, jobs, retry a korekce — živý snapshot není execution ledger

**Živá data:** ingest atributy evidují přijetí; analysis má aktuální `processing_status` a `updated_at`. Kontrola neprokázala uloženou historii runů/pokusů ani samostatných stránek. Neznamená to, že nemůže existovat v jiném systému.

**Komponenta:** pod syntetickými `pk/sk` ukládá jobs (`pk=JOBS, sk=job_id`) včetně attempts/owner/lease/config, dokumentový processing status, corrections (`pk=CORRECTIONS#document_id`). Retry může ponechat partial výsledek a vrátit job do queued v témže runu.

**Dopad:** neexistuje prosté mapování jednoho analysis řádku na tyto entity. `updated_at` neurčuje start/end OCR, page progress ani heartbeat. Není bezpečné zaměnit auditní history table za storage autoritu runtime jobů nebo ručních business oprav.

**Směr nápravy:** rozlišit business snapshot, execution state a audit. Stávající business status/korekce se auditem nepřesouvají ani nezapisují jinak; nové události přebírá audit listener bokem. Bez prokázané historie `history_available=false`, nikoli nulové trvání či smyšlené run ID. U source-runtime integrace zvlášť rozhodnout perzistenci jobs a oprav kompatibilně s business ownership.

Zdroj: `repository.py`, `service.py:80–123,125–154`, `pipeline.py:27–148`.

## 7. Rozhraní pro čtení a deployment ownership

Zdrojové Document API, existující ingest list a návrhový validator-agent API mají podobné URL paths pro documents, ale jiné odpovědi a service ownery. Ingest list poskytuje upload metadata; validator kontrakt klasifikaci/text; source `get_result` vrací bohatý JSON se stránkami a extraction. Společné `case_id/document_id` z nich nedělá jedno API. Validator kontrakt sám uvádí, že implementace není nasazená.

Vybraný AWS inventory při předchozím průzkumu ukázal existující ingest App Runner a case-client Lambda a tabulkové stacky; neprokázal processing SAM worker/frontu. To **neprokazuje neexistenci externího nebo ručního producenta analýz**. Je potřeba zjistit kdo je píše, z jaké verze a s jakým publish kontraktem; nelze nápravu zaměnit za prosté nasazení celého source SAM s další sadou business tabulek/originálů.

**Směr nápravy:** jmenovat producenta a integrační hranici, určit API base/service pro každý kontrakt a testovat skutečný mapping. Auditní API připojit ke stávající službě/routeru a UI; nezakládat novou aplikaci ani přesměrováním URL skrytě neměnit existující business kontrakt.

Zdroj: `be-intake/openapi-ingest.yaml`, `be-document-processing/contracts/openapi-ingest.json`, `be-document-processing/VALIDATOR-AGENT.md`, `be-document-processing/template.yaml`.

## Co se shoduje a nemá se zbytečně měnit

Společná identita je konceptuálně case/document (přesto source create_upload přiděluje jiné ID); soubory a velké výsledky patří do S3; case/client repository ve zdroji čte přímo přes `case_id`/`client_id`, nikoli přes dokumentové pk/sk. Omezení regionu Frankfurt `eu-central-1` je v souladu. Nesoulad dokumentového adapteru se tedy nemá plošně přenášet na case/client repository ani řešit přepracováním celého systému.

## Požadovaný výstup následné nápravy (zde neprováděné)

1. Potvrzený vlastník ingest a analysis zápisů, explicitní mapping po polích, rozlišení existujícího business výsledku a případných nových výstupů.
2. Adapter komponenty nad současným business kontraktem bez změny historických dat, klíčů, ID či objektů. Nepřebalit data do source payload modelu.
3. Oddělené rozhodnutí execution persistence versus audit; audit interně v `be-document-processing/src/document_processing/audit/`, nikoli nový app/root modul.
4. Hermetické fixtures přesných existujících Dynamo row shapes, chybějících volitelných polí, unknown legacy history, S3 reference typů a různých identit ingestu. Prokázat, že audit business zápisy ani výsledky nemění.
5. Teprve samostatně autorizovaný integrační/deployment postup; žádné replay existujících dokumentů, live inference nebo migrace z tohoto soupisu.

Tento dokument pouze zaznamenává konkrétní kontraktové odlišnosti pro návrhové rozhodnutí. Neurčuje dosud neznámého živého producenta a neslibuje hotovou opravu. Automatický opravný task zde není založen: aktuální zadání je upravit návrh a vypsat rozdíly; volba skutečného producenta a integračního scope je stále otevřená a není podložené nahrazovat ji implementačním odhadem.
