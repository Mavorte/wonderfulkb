import { useEffect, useState } from "react";
import type { DocumentApi } from "../api/createDocumentApi";
import FieldCorrection from "./FieldCorrection";
import type { DocumentResult, Evidence } from "./types";

export default function DocumentReview({ api, caseId, documentId, onCorrected, onClose }: {
  api: DocumentApi; caseId: string; documentId: string; onCorrected: () => void; onClose: () => void;
}) {
  const [result, setResult] = useState<DocumentResult>();
  const [image, setImage] = useState<string>();
  const [page, setPage] = useState(1);
  const [evidence, setEvidence] = useState<Evidence>();
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState<string>();
  useEffect(() => {
    let active = true;
    api.getResult(caseId, documentId).then((value) => { if (active) setResult(value); })
      .catch(() => { if (active) setError("Výsledek není dostupný."); });
    return () => { active = false; };
  }, [api, caseId, documentId, refresh]);
  useEffect(() => {
    let active = true;
    setImage(undefined);
    api.getPreview(caseId, documentId, page).then((value) => { if (active) setImage(value.image_url); })
      .catch(() => { if (active) setError("Náhled stránky zatím není dostupný."); });
    return () => { active = false; };
  }, [api, caseId, documentId, page]);

  function exportJson() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `${documentId}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const bbox = evidence?.page_number === page ? evidence.bbox : null;
  const currentPage = result?.ocr.pages.find((p) => p.page_number === page);
  return <section className="bo-review" aria-label="Výsledek dokumentu">
    <div className="bo-review-heading"><h3>Přepis a vytěžené údaje</h3>
      <button type="button" className="kb-btn kb-btn--tertiary kb-btn--small" onClick={onClose}>Zavřít</button>
    </div>
    {error && <p role="alert" className="bo-error">{error}</p>}
    {!result ? <p role="status">Načítání výsledku…</p> : <>
      <p>Typ dokumentu: {result.extraction.document_type}</p>
      <button type="button" className="kb-btn kb-btn--tertiary kb-btn--small" onClick={exportJson}>Stáhnout výsledek JSON</button>
      <div className="bo-review-grid">
        <div>
          <label>Strana <select value={page} onChange={(e) => { setPage(Number(e.target.value)); setEvidence(undefined); }}>
            {result.ocr.pages.map((p) => <option key={p.page_number} value={p.page_number}>{p.page_number}</option>)}
          </select> z {result.page_count}</label>
          <p>{currentPage?.method === "native" ? "Textová vrstva PDF" : "Vizuální přepis"}
            {currentPage?.model ? ` · ${currentPage.model}` : ""}</p>
          <div className="bo-page-image">
            {image && <img src={image} alt={`Originální strana ${page}`} />}
            {image && bbox && <span className="bo-evidence-box" style={{ left: `${bbox[0] * 100}%`, top: `${bbox[1] * 100}%`, width: `${(bbox[2] - bbox[0]) * 100}%`, height: `${(bbox[3] - bbox[1]) * 100}%` }} />}
          </div>
          {evidence && <blockquote>{evidence.quote}</blockquote>}
          <details><summary>Text stránky</summary><pre className="bo-transcript">{currentPage?.text}</pre></details>
        </div>
        <div className="bo-fields">
          {!result.extraction.fields.length && <p>Nebyly vytěženy žádné doložené údaje. Přepis je dostupný vlevo.</p>}
          {result.extraction.fields.map((field) => <article key={field.field_id} className="bo-field-result">
            <strong>{field.key}{field.role ? ` · ${field.role}` : ""}</strong>
            <p>{field.normalized_value ?? "Neurčeno"} {field.currency ?? ""}</p>
            <p>Původní zápis: {field.raw_value ?? "Nečitelný nebo nenalezený"}</p>
            <small>{field.status === "ambiguous" ? "Nejistý údaj – vyžaduje kontrolu" : field.status === "human_corrected" ? "Ručně opraveno" : field.status}</small>
            <div>{field.evidence.map((source, i) => <button type="button" key={i} className="kb-btn kb-btn--tertiary kb-btn--small" onClick={() => { setPage(source.page_number); setEvidence(source); }}>Zdroj na straně {source.page_number}</button>)}</div>
            <FieldCorrection api={api} caseId={caseId} documentId={documentId} runId={result.run_id} field={field}
              onSaved={() => { setRefresh((v) => v + 1); onCorrected(); }} />
          </article>)}
        </div>
      </div>
      {result.errors.length > 0 && <details open><summary>Chyby zpracování</summary><ul>{result.errors.map((e, i) => <li key={i}>{e.page_number ? `Strana ${e.page_number}: ` : ""}{e.code}</li>)}</ul></details>}
      {result.corrections.length > 0 && <details><summary>Historie oprav ({result.corrections.length})</summary><ul>{result.corrections.map((c) => <li key={c.correction_id}>{c.previous_value ?? "Neurčeno"} → {c.normalized_value ?? "Neurčeno"} · {c.reason} · {new Date(c.created_at).toLocaleString("cs-CZ")}</li>)}</ul></details>}
    </>}
  </section>;
}
