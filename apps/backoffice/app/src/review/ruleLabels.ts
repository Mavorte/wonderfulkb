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
  recipient_consistent: "Recipient details match",
  supplier_consistent: "Supplier details match",
  provider_consistent: "Provider (SGEF) details match",
  asset_consistent: "Financed asset matches",
  amounts_consistent: "Amounts match",
  contract_number_consistent: "Contract number matches",
  guarantor_consistent: "Guarantor details match",
  client_status_valid: "Client active, KYC and signatories",
};

export const rawStatusLabel: Record<string, string> = {
  passed: "Passed",
  missing: "Missing",
  conflict: "Conflict",
  failed: "Failed",
  cannot_verify: "Can't verify",
  not_applicable: "Not applicable",
  pending: "Pending",
};
