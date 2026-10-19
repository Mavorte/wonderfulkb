import { useState, type FormEvent } from "react";
import type { DocumentApi } from "../api/createDocumentApi";
import type { ExtractedField } from "./types";

export default function FieldCorrection({ api, caseId, documentId, runId, field, onSaved }: {
  api: DocumentApi; caseId: string; documentId: string; runId: string; field: ExtractedField; onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(field.normalized_value ?? "");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();
  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await api.correct(caseId, documentId, runId, field.field_id, value || null, reason);
      setOpen(false);
      onSaved();
    } catch { setError("Opravu se nepodařilo uložit. Ověřte formát hodnoty a důvod opravy."); }
    finally { setSaving(false); }
  }
  return open ? <form onSubmit={save} className="bo-correction">
    <label>Opravená hodnota<input className="kb-input" value={value} onChange={(e) => setValue(e.target.value)} /></label>
    <label>Důvod opravy<input className="kb-input" required minLength={3} value={reason} onChange={(e) => setReason(e.target.value)} /></label>
    <button className="kb-btn kb-btn--secondary kb-btn--small" disabled={saving}>Uložit opravu</button>
    <button type="button" className="kb-btn kb-btn--tertiary kb-btn--small" disabled={saving} onClick={() => setOpen(false)}>Zrušit</button>
    {error && <p role="alert">{error}</p>}
  </form> : <button type="button" className="kb-btn kb-btn--tertiary kb-btn--small" onClick={() => setOpen(true)}>Opravit</button>;
}
