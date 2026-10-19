import { useEffect, useRef, useState, type FormEvent } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import createDocumentApi from "../api/createDocumentApi";
import ClientCombobox from "../clients/ClientCombobox";
import type { Client } from "../clients/mockClients";
import CaseDocuments from "../documents/CaseDocuments";
import createCase, { type Case } from "./createCase";

const documentTypes = [["loan_agreement", "Úvěrová smlouva"], ["invoice", "Faktura"], ["handover", "Předávací protokol"], ["insurance", "Pojištění"], ["guarantee", "Ručení"]];

export default function NewCasePage() {
  const { track } = useWonderful();
  const trackRef = useRef(track);
  trackRef.current = track;
  const [api] = useState(() => createDocumentApi());
  const [clients, setClients] = useState<Client[]>([]);
  const [client, setClient] = useState<Client | null>(null);
  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState<Case | null>(null);
  const [required, setRequired] = useState(["loan_agreement", "invoice"]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const requestId = useRef<string | null>(null);

  useEffect(() => {
    let active = true;
    trackRef.current("new_case_opened");
    api.getClients().then((items) => { if (active) setClients(items); })
      .catch(() => { if (active) setError("Klienty se nepodařilo načíst. Ověřte připojení dokumentové služby."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    let active = true;
    setCases([]);
    setSelectedCase(null);
    requestId.current = null;
    if (client) api.getCases(client.id).then((result) => { if (active) setCases(result.cases); })
      .catch(() => { if (active) setError("Seznam případů se nepodařilo načíst."); });
    return () => { active = false; };
  }, [api, client]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!client) return setError("Vyberte firmu.");
    if (!required.length) return setError("Vyberte alespoň jeden požadovaný podklad.");
    setSubmitting(true);
    setError(undefined);
    track("case_create_started");
    requestId.current ??= `case-${crypto.randomUUID()}`;
    try {
      const created = await createCase(client, requestId.current, required, api);
      setCases((items) => [created, ...items.filter((item) => item.case_id !== created.case_id)]);
      setSelectedCase(created);
      requestId.current = null;
      track("case_create_completed");
    } catch {
      setError("Případ se nepodařilo vytvořit. Opakované odeslání použije stejné ID.");
      track("case_create_failed");
    } finally { setSubmitting(false); }
  }

  return <>
    <h1 className="bo-title">Kontrola firemní dokumentace</h1>
    <form className="bo-card" onSubmit={submit}>
      <ClientCombobox clients={clients} value={client} disabled={loading || submitting} error={error}
        onChange={(value) => { setClient(value); setError(undefined); }} />
      {loading && <p role="status">Načítání firem…</p>}
      <fieldset className="bo-required"><legend>Požadované podklady pro nový případ</legend>
        {documentTypes.map(([key, label]) => <label key={key}>
          <input type="checkbox" checked={required.includes(key)} disabled={submitting}
            onChange={(e) => setRequired((items) => e.target.checked ? [...items, key] : items.filter((item) => item !== key))} /> {label}
        </label>)}
      </fieldset>
      <div className="bo-actions"><button className="kb-btn kb-btn--primary" disabled={loading || submitting || !client}>
        {submitting ? "Zakládání…" : "Založit případ"}
      </button></div>
    </form>
    {client && cases.length > 0 && <section className="bo-case-list" aria-label="Případy firmy">
      <h2>Případy: {client.name}</h2>
      {cases.map((item) => <button key={item.case_id} type="button" className="kb-btn kb-btn--tertiary"
        aria-pressed={selectedCase?.case_id === item.case_id} onClick={() => setSelectedCase(item)}>
        {item.case_id} · {new Date(item.created_at).toLocaleDateString("cs-CZ")}
      </button>)}
    </section>}
    {selectedCase && client && <CaseDocuments key={selectedCase.case_id} api={api} caseId={selectedCase.case_id} client={client} />}
  </>;
}
