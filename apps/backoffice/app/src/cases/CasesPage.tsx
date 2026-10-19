import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import CaseDetail from "./CaseDetail";
import formatDate from "./formatDate";
import getErrorCode from "../getErrorCode";
import getCase, { type CaseDetail as CaseDetailData } from "./getCase";
import listCases, { type CaseSummary } from "./listCases";

type Props = { onNewCase: () => void };

export default function CasesPage({ onNewCase }: Props) {
  const { api, track } = useWonderful();
  const apiRef = useRef(api);
  apiRef.current = api;
  const trackRef = useRef(track);
  trackRef.current = track;
  const opened = useRef(false);
  const [cases, setCases] = useState<CaseSummary[]>();
  const [nextToken, setNextToken] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadMoreError, setLoadMoreError] = useState(false);
  const [lookupId, setLookupId] = useState("");
  const [lookupError, setLookupError] = useState<string>();
  const [lookingUp, setLookingUp] = useState(false);
  const [detail, setDetail] = useState<CaseDetailData>();
  const lookupRequest = useRef(0);

  const load = useCallback(() => {
    setError(false);
    setCases(undefined);
    listCases(apiRef.current).then(
      (page) => {
        setCases(page.cases);
        setNextToken(page.nextToken);
      },
      () => setError(true),
    );
  }, []);

  useEffect(() => {
    if (!opened.current) {
      opened.current = true;
      trackRef.current("cases_opened");
    }
    load();
  }, [load]);

  const loadMore = async () => {
    setLoadingMore(true);
    setLoadMoreError(false);
    try {
      const page = await listCases(api, nextToken);
      setCases((current) => [...(current ?? []), ...page.cases]);
      setNextToken(page.nextToken);
    } catch {
      setLoadMoreError(true);
    } finally {
      setLoadingMore(false);
    }
  };

  // Only the latest lookup shows, even when an earlier one answers later.
  const openCase = async (caseId: string) => {
    const request = ++lookupRequest.current;
    setLookupError(undefined);
    setLookingUp(true);
    try {
      const found = await getCase(api, caseId);
      if (request === lookupRequest.current) setDetail(found);
    } catch (e) {
      if (request !== lookupRequest.current) return;
      setDetail(undefined);
      setLookupError(
        getErrorCode(e) === "case_not_found"
          ? `No case has the ID “${caseId}”.`
          : "The case could not be loaded. Try again.",
      );
    } finally {
      if (request === lookupRequest.current) setLookingUp(false);
    }
  };

  const onLookup = (e: FormEvent) => {
    e.preventDefault();
    const caseId = lookupId.trim();
    if (!caseId) return setLookupError("Enter a case ID.");
    void openCase(caseId);
  };

  return (
    <>
      <div className="bo-heading">
        <h1 className="bo-title">All cases</h1>
        <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={onNewCase}>
          New case
        </button>
      </div>
      <div className="bo-card bo-card--wide">
        <form className="bo-lookup" onSubmit={onLookup} noValidate>
          <div className="kb-field">
            <label htmlFor="bo-case-lookup">Find case by ID</label>
            <input
              id="bo-case-lookup"
              className="kb-input"
              type="text"
              autoComplete="off"
              placeholder="e.g. 3f2b8c1e-7d4a-4b6e-9a0c-5e1f2d3c4b5a"
              value={lookupId}
              aria-invalid={lookupError ? true : undefined}
              aria-describedby={lookupError ? "bo-case-lookup-error" : undefined}
              onChange={(e) => {
                setLookupId(e.target.value);
                setLookupError(undefined);
              }}
            />
          </div>
          <button
            type="submit"
            className={`kb-btn kb-btn--secondary${lookingUp ? " is-loading" : ""}`}
            aria-busy={lookingUp}
            disabled={lookingUp}
          >
            Find
          </button>
        </form>
        {lookupError && (
          <p id="bo-case-lookup-error" className="kb-field__error bo-field-error" role="alert">
            {lookupError}
          </p>
        )}
        {detail && <CaseDetail detail={detail} onClose={() => setDetail(undefined)} />}

        <div aria-busy={!cases && !error}>
          {error ? (
            <div className="bo-empty" role="alert">
              <p>The cases could not be loaded.</p>
              <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={load}>
                Try again
              </button>
            </div>
          ) : !cases ? (
            <p className="bo-empty">Loading cases…</p>
          ) : cases.length === 0 ? (
            <div className="bo-empty">
              <p>No cases yet.</p>
              <button type="button" className="kb-btn kb-btn--primary kb-btn--small" onClick={onNewCase}>
                Create the first case
              </button>
            </div>
          ) : (
            <div className="bo-table-wrap">
              <table className="bo-table">
                <caption className="bo-table__caption">
                  {cases.length}
                  {nextToken ? "+" : ""} {cases.length === 1 ? "case" : "cases"}, newest first
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Case</th>
                    <th scope="col">Client</th>
                    <th scope="col">Status</th>
                    <th scope="col">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <button type="button" className="bo-link bo-table__strong" onClick={() => openCase(c.id)}>
                          {c.id}
                        </button>
                      </td>
                      <td>
                        <span className="bo-table__strong">{c.clientName ?? c.clientId}</span>
                        {c.clientIco && <span className="bo-table__meta">IČO {c.clientIco}</span>}
                      </td>
                      <td>{c.status}</td>
                      <td>{formatDate(c.createdAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {cases && nextToken && !error && (
            <div className="bo-actions bo-actions--more">
              <button
                type="button"
                className={`kb-btn kb-btn--secondary kb-btn--small${loadingMore ? " is-loading" : ""}`}
                aria-busy={loadingMore}
                disabled={loadingMore}
                onClick={loadMore}
              >
                Load more
              </button>
              {loadMoreError && (
                <p className="kb-field__error bo-field-error" role="alert">
                  More cases could not be loaded. Try again.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
