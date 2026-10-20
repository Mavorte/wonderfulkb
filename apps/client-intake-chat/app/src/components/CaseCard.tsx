import type { ChatPageData } from "../types";

type Field = { label: string; value: unknown };

export default function CaseCard({ data }: { data: ChatPageData }) {
  const metadata = data.case.metadata ?? {};
  const fields: Field[] = [
    { label: "Client", value: data.client?.name },
    { label: "IČO", value: data.client?.ico },
    { label: "Loan agreement", value: metadata.loan_number },
    { label: "Financed asset", value: metadata.asset },
    { label: "Case ID", value: data.case.case_id },
  ];
  const visible = fields.filter((f) => f.value !== undefined && f.value !== null && f.value !== "");

  return (
    <section className="app-card">
      <div className="app-card__head">
        <h2 className="app-card__title">Your case</h2>
        {data.is_mock && <span className="kb-badge kb-badge--dark">Demo data</span>}
      </div>
      <dl className="app-fields">
        {visible.map((f) => (
          <div key={f.label}>
            <dt>{f.label}</dt>
            <dd>{String(f.value)}</dd>
          </div>
        ))}
      </dl>
      <ol className="app-steps">
        <li>Drag your loan agreement into the chat.</li>
        <li>The assistant tells you which documents the agreement asks for.</li>
        <li>Drag those documents into the chat. Each one is checked when it arrives.</li>
        <li>When everything is in, the documents are sent to KB.</li>
      </ol>
    </section>
  );
}
