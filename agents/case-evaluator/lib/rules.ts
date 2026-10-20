// The business rules an evaluation records, one evaluate_* tool each. A run is
// complete when every rule here has a result. Later phases add rules here.

export const RULES = {
  loan_agreement_present: "A loan agreement (smlouva o úvěru) is among the documents.",
  required_documents_present: "Every document the loan agreement requires before disbursement is present.",
  recipient_matches_client: "The recipient's name and IČO in the loan agreement match the client record.",
  invoice_contents: "The invoice / tax document has its mandatory contents.",
  purchase_contract_contents: "The purchase contract or order has its mandatory contents and both parties' signatures.",
  handover_protocol_contents: "The handover protocol / delivery note has its mandatory contents and both parties' signatures.",
  technical_specification_contents: "The technical specification identifies the product.",
  payment_proof_contents: "The bank statement / payment proof has its mandatory contents.",
  security_transfer_contents: "The security transfer of ownership has its mandatory contents and signatures.",
  insurance_vinculation_contents: "The insurance vinculation has its mandatory contents and the insurer's signature.",
  guarantee_contents: "The guarantee declaration has its mandatory contents and signatures.",
  recipient_consistent: "The recipient's name, IČO, DIČ and address are the same in every document and in the client record.",
  client_status_valid: "The client is active with valid KYC, and the people signing for the recipient are its authorized signatories.",
  supplier_consistent: "The supplier's name, IČO, DIČ, address and bank account are the same in every document.",
  provider_consistent: "The provider's name, IČO, DIČ and bank account are the same in every document.",
  asset_consistent: "The financed asset's name, manufacturer, serial number/VIN and year are the same in every document and in the case record.",
  amounts_consistent: "The price, VAT and loan amount are the same in every document.",
  contract_number_consistent: "The loan contract number is the same in every document and in the case record.",
  guarantor_consistent: "The guarantor's name, IČO and address are the same in every document.",
} as const;

export type RuleId = keyof typeof RULES;

export const RULE_IDS = Object.keys(RULES) as RuleId[];

export type Status = "passed" | "missing" | "conflict" | "cannot_verify" | "not_applicable";

export type Verdict = "ready" | "needs_correction" | "needs_review";

// Kinds of required documents (business_rules.docx). required_documents_present
// tags each requirement with one; the matching *_contents rule then checks it.
export const DOCUMENT_TYPES = [
  "invoice",
  "purchase_contract",
  "handover_protocol",
  "technical_specification",
  "payment_proof",
  "security_transfer",
  "insurance_vinculation",
  "guarantee",
  "other",
] as const;

export type DocumentType = (typeof DOCUMENT_TYPES)[number];

// not_applicable counts like passed.
export function getVerdict(statuses: string[]): Verdict {
  if (statuses.some((s) => s === "missing" || s === "conflict")) return "needs_correction";
  if (statuses.some((s) => s === "cannot_verify")) return "needs_review";
  return "ready";
}
