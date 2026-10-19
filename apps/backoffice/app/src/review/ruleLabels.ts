// Display names for case-evaluator rule ids and result statuses.

export const ruleLabels: Record<string, string> = {
  loan_agreement_present: "Loan agreement present",
  required_documents_present: "Required documents present",
  recipient_matches_client: "Recipient matches client record",
  purchase_contract_contents: "Purchase order / contract",
  invoice_contents: "Invoice",
  handover_protocol_contents: "Handover protocol",
  insurance_vinculation_contents: "Insurance vinculation",
  security_transfer_contents: "Security transfer of ownership",
  guarantee_contents: "Guarantee declaration",
  payment_proof_contents: "Proof of payment",
  technical_specification_contents: "Technical specification",
};

export const rawStatusLabel: Record<string, string> = {
  passed: "Passed",
  missing: "Missing",
  conflict: "Conflict",
  failed: "Failed",
  cannot_verify: "Can't verify",
  not_applicable: "Not applicable",
};
