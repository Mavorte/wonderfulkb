import { useEffect, useRef, useState, type FormEvent } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import ClientCombobox from "../clients/ClientCombobox";
import searchClients, { type Client } from "../clients/searchClients";
import getErrorCode from "../getErrorCode";
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
  const [copy, setCopy] = useState<"copied" | "failed">();

  const onCopy = async (link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
  };

  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    trackRef.current("new_case_opened");
  }, []);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!client) return;
    setSubmitting(true);
    track("case_create_started");
    try {
      const result = await createCase(api, client);
      track("case_create_completed");
      setCreated({ case: result, client });
      setCopy(undefined);
      setClient(null);
    } catch (e) {
      track("case_create_failed");
      setError(
        getErrorCode(e) === "client_not_active"
          ? "This client is not active, so no case can be created for them."
          : "The case could not be created. Try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <h1 className="bo-title">New case</h1>
      <form className="bo-card bo-card--full" onSubmit={onSubmit} noValidate>
        <ClientCombobox
          search={(query) => searchClients(api, query)}
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
            disabled={submitting || !client}
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
              <span className="bo-success__body">
                <strong>Case created for {created.client.name}.</strong>
                <dl className="bo-success__list">
                  <dt>Case ID</dt>
                  <dd>
                    <code>{created.case.id}</code>
                  </dd>
                  <dt>Client link</dt>
                  <dd>
                    {created.case.link ? (
                      <span className="bo-link">
                        <code>{created.case.link}</code>
                        <button
                          type="button"
                          className="kb-btn kb-btn--secondary kb-btn--small"
                          onClick={() => onCopy(created.case.link!)}
                        >
                          {copy === "copied" ? "Copied" : "Copy link"}
                        </button>
                        {copy === "failed" && <span>Copy failed. Select the link and copy it.</span>}
                      </span>
                    ) : (
                      "Could not be created."
                    )}
                  </dd>
                </dl>
              </span>
            </p>
          )}
        </div>
      </form>
    </>
  );
}
