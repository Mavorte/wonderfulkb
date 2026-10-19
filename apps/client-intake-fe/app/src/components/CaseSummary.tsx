import type { IntakeData } from "../types";
import KbIcon from "./KbIcon";

type Field = { label: string; value: unknown };

function FieldList({ fields }: { fields: Field[] }) {
  const visible = fields.filter((f) => f.value !== undefined && f.value !== null && f.value !== "");
  if (visible.length === 0) return <p className="app-empty">No details available.</p>;
  return (
    <dl className="app-fields">
      {visible.map((f) => (
        <div key={f.label}>
          <dt>{f.label}</dt>
          <dd>{String(f.value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function RequiredDocuments({ data }: { data: IntakeData }) {
  const requiredDocuments = data.case.metadata?.required_documents;
  if (!Array.isArray(requiredDocuments) || requiredDocuments.length === 0) return null;
  return (
    <section className="app-card">
      <div className="app-card__head">
        <h2 className="app-card__title">Documents we need from you</h2>
      </div>
      <ul className="app-list app-card__body">
        {requiredDocuments.map(String).map((doc) => (
          <li key={doc}>
            <KbIcon name="file" className="kb-icon--accent" />
            {doc}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function CaseSummary({ data }: { data: IntakeData }) {
  const metadata = data.case.metadata ?? {};
  const client = data.client;

  return (
    <div className="app-grid">
      <section className="app-card">
        <div className="app-card__head">
          <h2 className="app-card__title">Case</h2>
          {data.is_mock && <span className="kb-badge kb-badge--dark">Demo data</span>}
        </div>
        <FieldList
          fields={[
            { label: "Case ID", value: data.case.case_id },
            { label: "Loan agreement", value: metadata.loan_number },
            { label: "Financed asset", value: metadata.asset },
            { label: "Serial number", value: metadata.serial_number },
          ]}
        />
      </section>
      <section className="app-card">
        <div className="app-card__head">
          <h2 className="app-card__title">Client</h2>
        </div>
        <FieldList
          fields={[
            { label: "Name", value: client?.name },
            { label: "IČO", value: client?.ico },
            { label: "DIČ", value: client?.dic },
            { label: "Address", value: client?.address },
          ]}
        />
      </section>
    </div>
  );
}
