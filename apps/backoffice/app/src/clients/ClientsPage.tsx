import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWonderful } from "@wonderful/app-sdk";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import CaseStatusPill from "../cases/CaseStatusPill";
import formatDate from "../cases/formatDate";
import listClientDirectory, { type DirectoryClient } from "./listClientDirectory";

function normalize(text: string): string {
  return text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

export default function ClientsPage() {
  const { api, track } = useWonderful();
  const apiRef = useRef(api);
  apiRef.current = api;
  const trackRef = useRef(track);
  trackRef.current = track;
  const opened = useRef(false);
  const [allClients, setAllClients] = useState<DirectoryClient[]>();
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const setQuery = (next: string) => setSearchParams(next ? { q: next } : {}, { replace: true });
  const selectedId = useParams<{ clientId: string }>().clientId;
  const navigate = useNavigate();
  // The filter stays in the query string while a client is opened or closed.
  const search = searchParams.toString() ? `?${searchParams}` : "";

  const load = useCallback(() => {
    setError(false);
    setAllClients(undefined);
    listClientDirectory(apiRef.current).then(
      (directory) => {
        setAllClients(directory.clients);
        setTruncated(directory.truncated);
      },
      () => setError(true),
    );
  }, []);

  useEffect(() => {
    if (!opened.current) {
      opened.current = true;
      trackRef.current("clients_opened");
    }
    load();
  }, [load]);

  const clients = useMemo(() => {
    const q = normalize(query.trim());
    if (!allClients || !q) return allClients;
    return allClients.filter((c) => normalize(c.name).includes(q) || c.ico.includes(q));
  }, [allClients, query]);
  const selected = allClients?.find((c) => c.id === selectedId);

  return (
    <>
      <div className="bo-heading">
        <h1 className="bo-title">Clients</h1>
      </div>
      <div className="bo-card bo-card--full bo-clients">
        <div className="bo-clients__toolbar">
          <div className="kb-field bo-clients__filter">
            <label htmlFor="bo-client-filter">Filter by name or IČO</label>
            <input
              id="bo-client-filter"
              className="kb-input"
              type="search"
              autoComplete="off"
              placeholder="e.g. Agroluh or 98007106"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {clients && clients.length > 0 && (
            <p className="bo-clients__count" aria-live="polite">
              {clients.length} {clients.length === 1 ? "client" : "clients"}
              {query.trim() && allClients && ` of ${allClients.length}`}
              {truncated && " (list cut short, not every client is shown)"}
            </p>
          )}
        </div>

        {selected && <ClientDetail client={selected} onClose={() => navigate(`/clients${search}`)} />}

        <div aria-busy={!clients && !error}>
          {error ? (
            <div className="bo-empty" role="alert">
              <p>The clients could not be loaded.</p>
              <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={load}>
                Try again
              </button>
            </div>
          ) : !clients ? (
            <p className="bo-empty">Loading clients…</p>
          ) : clients.length === 0 ? (
            <p className="bo-empty">{query.trim() ? `No client matches “${query.trim()}”.` : "No clients yet."}</p>
          ) : (
            <div className="bo-table-wrap">
              <table className="bo-table bo-table--clients">
                <caption className="bo-sr-only">Clients, by name</caption>
                <thead>
                  <tr>
                    <th scope="col">Client</th>
                    <th scope="col">Address</th>
                    <th scope="col">KYC</th>
                    <th scope="col" className="bo-table__num">Cases</th>
                    <th scope="col">Latest case · opened</th>
                  </tr>
                </thead>
                <tbody>
                  {clients.map((c) => (
                    <tr key={c.id} aria-selected={c.id === selectedId}>
                      <td>
                        <Link className="bo-clients__name" to={`/clients/${encodeURIComponent(c.id)}${search}`}>
                          {c.name}
                        </Link>
                        <span className="bo-table__meta">IČO {c.ico}</span>
                      </td>
                      <td className="bo-clients__address">{c.address ?? "—"}</td>
                      <td>
                        <KycStatus status={c.kycStatus} />
                      </td>
                      <td className="bo-table__num">{c.cases.length}</td>
                      <td>
                        {c.cases[0] ? (
                          <div className="bo-clients__case">
                            <CaseStatusPill status={c.cases[0].status} />
                            <span className="bo-clients__date">{formatDate(c.cases[0].createdAt)}</span>
                          </div>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function KycStatus({ status }: { status: string | null }) {
  if (status === "ok") return <span className="bo-pill bo-pill--ok">OK</span>;
  return <span className="bo-pill">{status ?? "Not checked"}</span>;
}

function ClientDetail({ client, onClose }: { client: DirectoryClient; onClose: () => void }) {
  return (
    <section className="bo-detail" aria-labelledby="bo-client-detail-title">
      <div className="bo-heading bo-heading--compact">
        <h2 id="bo-client-detail-title" className="bo-detail__title">
          {client.name}
        </h2>
        <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={onClose}>
          Close
        </button>
      </div>
      <dl className="bo-detail__list">
        <dt>IČO / DIČ</dt>
        <dd>
          {client.ico} / {client.dic ?? "—"}
        </dd>
        <dt>Legal form</dt>
        <dd>{client.legalForm ?? "—"}</dd>
        <dt>Address</dt>
        <dd>{client.address ?? "—"}</dd>
        <dt>Signatory</dt>
        <dd>{client.signatory ? `${client.signatory.name} (${client.signatory.function})` : "—"}</dd>
        <dt>Email</dt>
        <dd>{client.email ?? "—"}</dd>
        <dt>KYC</dt>
        <dd>
          <KycStatus status={client.kycStatus} />
          {client.kycCheckedAt && ` checked ${client.kycCheckedAt}`}
        </dd>
      </dl>
      {client.cases.length > 0 && (
        <table className="bo-table bo-detail__cases">
          <thead>
            <tr>
              <th scope="col">Status</th>
              <th scope="col">Opened</th>
            </tr>
          </thead>
          <tbody>
            {client.cases.map((c) => (
              <tr key={c.id}>
                <td>
                  <CaseStatusPill status={c.status} />
                </td>
                <td>{formatDate(c.createdAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
