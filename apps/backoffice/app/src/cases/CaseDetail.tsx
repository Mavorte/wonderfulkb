import type { CaseDetail as CaseDetailData } from "./getCase";
import formatDate from "./formatDate";

type Props = { detail: CaseDetailData; onClose: () => void };

export default function CaseDetail({ detail, onClose }: Props) {
  return (
    <section className="bo-detail" aria-labelledby="bo-detail-title">
      <div className="bo-heading bo-heading--compact">
        <h2 id="bo-detail-title" className="bo-detail__title">
          Case {detail.id}
        </h2>
        <button type="button" className="kb-btn kb-btn--secondary kb-btn--small" onClick={onClose}>
          Close
        </button>
      </div>
      <dl className="bo-detail__list">
        <dt>Client</dt>
        <dd>
          {detail.clientName ?? detail.clientId}
          {detail.clientIco && <span className="bo-table__meta">IČO {detail.clientIco}</span>}
          {detail.clientName && <span className="bo-table__meta">{detail.clientId}</span>}
        </dd>
        <dt>Status</dt>
        <dd>{detail.status}</dd>
        <dt>Created</dt>
        <dd>{formatDate(detail.createdAt)}</dd>
        <dt>Intake link hash</dt>
        <dd>{detail.hash ? <code>{detail.hash}</code> : "No intake link"}</dd>
      </dl>
    </section>
  );
}
