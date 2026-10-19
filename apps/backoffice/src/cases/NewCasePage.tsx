import { useState, type FormEvent } from "react";
import { ClientCombobox } from "../clients/ClientCombobox";
import { mockClients, type Client } from "../clients/mockClients";
import { createCase, type Case } from "./createCase";

export function NewCasePage() {
  const [client, setClient] = useState<Client | null>(null);
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<{ case: Case; client: Client }>();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!client) return setError("Select a client to create a case.");
    setSubmitting(true);
    const result = await createCase(client);
    setSubmitting(false);
    setCreated({ case: result, client });
    setClient(null);
  };

  return (
    <>
      <h1 className="bo-title">New case</h1>
      <form className="bo-card" onSubmit={onSubmit} noValidate>
        <ClientCombobox
          clients={mockClients}
          value={client}
          disabled={submitting}
          error={error}
          onChange={(c) => {
            setClient(c);
            setError(undefined);
            if (c) setCreated(undefined);
          }}
        />
        <div className="bo-actions">
          <button
            type="submit"
            className={`kb-btn kb-btn--primary${submitting ? " is-loading" : ""}`}
            aria-busy={submitting}
            disabled={submitting}
          >
            Create case
          </button>
        </div>
        <div role="status" aria-live="polite">
          {created && (
            <p className="bo-success">
              <svg className="kb-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M9.5 16.17 5.33 12l-1.41 1.41L9.5 19 20.5 8l-1.41-1.41L9.5 16.17Z" />
              </svg>
              <span>
                Case <strong>{created.case.id}</strong> created for {created.client.name}.
              </span>
            </p>
          )}
        </div>
      </form>
    </>
  );
}
