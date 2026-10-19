import { useEffect, useState, type ChangeEvent } from "react";
import type { DocumentApi } from "../api/createDocumentApi";
import type { Client } from "../clients/mockClients";
import DocumentReview from "./DocumentReview";
import type { CaseValidation, DocumentRecord } from "./types";

const states: Record<string, string> = {
  awaiting_upload: "Čeká na nahrání", queued: "Ve frontě", processing: "Zpracovává se",
  completed: "Zpracováno", partial: "Částečně zpracováno", failed: "Zpracování selhalo",
};

export default function CaseDocuments({ api, caseId, client }: { api: DocumentApi; caseId: string; client: Client }) {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [validation, setValidation] = useState<CaseValidation | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [mode, setMode] = useState<"visual" | "auto">("auto");
  const [error, setError] = useState<string>();

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function load() {
      try {
        const [list, report] = await Promise.all([api.getDocuments(caseId), api.getValidation(caseId)]);
        if (!active) return;
        setDocuments(list.documents);
        setValidation(report);
        if (list.documents.some((d) => ["queued", "processing"].includes(d.processing_status))) timer = setTimeout(load, 2000);
      } catch { if (active) setError("Stav dokumentů se nepodařilo načíst."); }
    }
    void load();
    return () => { active = false; if (timer) clearTimeout(timer); };
  }, [api, caseId, refresh]);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    setUploading(true);
    setError(undefined);
    try {
      for (const file of files) {
        await api.upload(caseId, file, mode);
        setRefresh((v) => v + 1);
      }
    } catch (e) { setError(e instanceof Error ? e.message : "Nahrávání selhalo."); }
    finally { setUploading(false); setRefresh((v) => v + 1); }
  }

  return <section className="bo-workspace" aria-label="Dokumenty případu">
    <h2>Dokumenty případu</h2>
    <p>{client.name} · IČO {client.ico} · <small>{caseId}</small></p>
    <div className="bo-upload">
      <label className="kb-field">Způsob čtení
        <select className="kb-input" value={mode} disabled={uploading} onChange={(e) => setMode(e.target.value as "visual" | "auto")}>
          <option value="auto">Nejdřív text PDF, skeny přečíst vizuálně</option>
          <option value="visual">Všechny stránky přečíst vizuálně</option>
        </select>
      </label>
      <label className="kb-field">Přidat PDF nebo fotografie
        <input type="file" multiple accept="application/pdf,image/png,image/jpeg" disabled={uploading} onChange={(e) => void upload(e)} />
      </label>
      <p>PDF, PNG nebo JPEG · nejvýše 25 MiB a 50 stran na soubor</p>
      {uploading && <p role="status">Nahrávání dokumentů…</p>}
    </div>
    {error && <p role="alert" className="bo-error">{error}</p>}
    <button type="button" className="kb-btn kb-btn--tertiary kb-btn--small" onClick={() => { setError(undefined); setRefresh((v) => v + 1); }}>Obnovit stav</button>
    <ul className="bo-documents">
      {documents.map((d) => <li key={d.document_id}>
        <div><strong>{d.filename}</strong><p>{states[d.processing_status]}{d.page_count ? ` · ${d.page_count} stran` : ""}</p>
          {(d.error || d.errors?.length) ? <p className="bo-error">{d.error ?? d.errors?.map((e) => e.code).join(", ")}</p> : null}
        </div>
        {["completed", "partial"].includes(d.processing_status) && <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={() => setSelected(d.document_id)}>Otevřít výsledek</button>}
      </li>)}
    </ul>
    {!documents.length && <p>Do případu zatím nebyly přidány dokumenty.</p>}
    {validation && <section className="bo-validation" aria-label="Kontroly případu">
      <h3>Kontroly napříč dokumenty</h3>
      <p>{validation.status === "issues_found" ? "Nalezeny údaje k prověření." : validation.status === "consistent" ? "Provedené kontroly nezjistily rozpor." : "Pro dokončení kontrol zatím chybí podklady nebo doložené údaje."}</p>
      {validation.completeness_profile === "not_configured" && <p>Není nastaven seznam požadovaných podkladů.</p>}
      {validation.findings.map((finding, i) => <div className="bo-finding" key={`${finding.code}-${i}`}>
        <strong>{finding.message}</strong>
        <div>{finding.sources.filter((s) => s.document_id).map((source, n) => <button key={n} type="button" className="kb-btn kb-btn--tertiary kb-btn--small" onClick={() => setSelected(source.document_id!)}>Otevřít zdroj {n + 1}</button>)}</div>
      </div>)}
    </section>}
    {selected && <DocumentReview key={selected} api={api} caseId={caseId} documentId={selected}
      onCorrected={() => setRefresh((v) => v + 1)} onClose={() => setSelected(null)} />}
  </section>;
}
