import { useEffect, useRef, useState, type FormEvent } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import ClientCombobox from "../clients/ClientCombobox";
import { mockClients, type Client } from "../clients/mockClients";
import createCase, { type Case } from "./createCase";

export default function NewCasePage() {
  const { api, track } = useWonderful();
  const trackRef = useRef(track);
  trackRef.current = track;
  const opened = useRef(false);
  const [client, setClient] = useState<Client | null>(null);
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<{ case: Case; client: Client }>();

  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    trackRef.current("new_case_opened");
  }, []);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!client) return setError("Select a client to create a case.");
    setSubmitting(true);
    track("case_create_started");
    try {
      const result = await createCase(api, client);
      track("case_create_completed");
      setCreated({ case: result, client });
      setClient(null);
    } catch {
      track("case_create_failed");
      setError("The case could not be created. Try again.");
    } finally {
      setSubmitting(false);
    }
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
                Case <strong>{created.case.id}</strong> created for {created.client.name}. Intake link
                hash: <code>{created.case.hash}</code>
              </span>
            </p>
          )}
        </div>
      </form>
    </>
  );
}
