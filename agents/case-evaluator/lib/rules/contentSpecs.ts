// Mandatory contents per document type, from business_rules.docx. Each spec is
// one *_contents rule; its evaluate tool is tools/evaluate_<rule_id>/.

import type { ContentsSpec } from "./contents";

const SGEF = { role: "provider", min: 2, label: "SGEF (two signatories)" } as const;

export const INVOICE: ContentsSpec = {
  rule_id: "invoice_contents",
  document_type: "invoice",
  document_name: "invoice / tax document (faktura, daňový doklad)",
  fields: [
    { key: "issuer", label: "issuer identity (vystavitel / dodavatel: name, IČO, address)" },
    { key: "customer", label: "customer identity (odběratel / příjemce: name, IČO, address)" },
    { key: "number", label: "document number (číslo dokladu)" },
    { key: "subject", label: "subject of supply (předmět plnění)" },
    { key: "price", label: "price (cena)" },
    { key: "vat", label: "VAT (DPH), or why none is charged" },
    { key: "issue_date", label: "issue date (datum vystavení)" },
    { key: "supply_date", label: "date of taxable supply (DUZP)", optional: true },
    { key: "due_date", label: "due date (splatnost)" },
    { key: "payment_details", label: "payment details (bank account, variable symbol)", optional: true },
  ],
  signatures: [],
};

export const PURCHASE_CONTRACT: ContentsSpec = {
  rule_id: "purchase_contract_contents",
  document_type: "purchase_contract",
  document_name: "purchase contract or order (kupní smlouva, objednávka)",
  fields: [
    { key: "buyer", label: "buyer (kupující / objednatel: name, IČO)" },
    { key: "seller", label: "seller (prodávající / dodavatel: name, IČO)" },
    { key: "subject", label: "unambiguous subject of purchase (předmět koupě)" },
    { key: "price", label: "purchase price (kupní cena)" },
  ],
  signatures: [
    { role: "borrower", min: 1, label: "buyer" },
    { role: "supplier", min: 1, label: "seller (signature or confirmation)" },
  ],
};

export const HANDOVER_PROTOCOL: ContentsSpec = {
  rule_id: "handover_protocol_contents",
  document_type: "handover_protocol",
  document_name: "handover protocol or delivery note (předávací protokol, dodací list)",
  fields: [
    { key: "handed_over_by", label: "who hands over (předávající / dodavatel)" },
    { key: "received_by", label: "who receives (přebírající / příjemce)" },
    { key: "asset", label: "asset identification (předmět, výrobní číslo)" },
    { key: "handover_date", label: "handover date (datum předání / převzetí)" },
    { key: "condition", label: "condition or quantity (stav nebo množství)" },
  ],
  signatures: [
    { role: "supplier", min: 1, label: "handing-over party" },
    { role: "borrower", min: 1, label: "receiving party" },
  ],
};

export const TECHNICAL_SPECIFICATION: ContentsSpec = {
  rule_id: "technical_specification_contents",
  document_type: "technical_specification",
  document_name: "technical specification (technická specifikace)",
  fields: [
    { key: "product", label: "product identification (předmět)" },
    { key: "model", label: "model / type" },
    { key: "manufacturer", label: "manufacturer (výrobce)" },
    { key: "parameters", label: "technical parameters" },
    { key: "serial_number", label: "serial number / VIN", optional: true },
  ],
  signatures: [],
};

export const PAYMENT_PROOF: ContentsSpec = {
  rule_id: "payment_proof_contents",
  document_type: "payment_proof",
  document_name: "bank statement or payment proof (výpis z účtu, potvrzení o úhradě)",
  fields: [
    { key: "payer_account", label: "payer's account (účet plátce)" },
    { key: "payee_account", label: "payee's account (účet příjemce)" },
    { key: "amount", label: "amount (částka)" },
    { key: "currency", label: "currency (měna)" },
    { key: "date", label: "transaction date (datum transakce)" },
    { key: "reference", label: "link to the invoice or financing (variable symbol, invoice number, message)" },
  ],
  signatures: [],
};

export const SECURITY_TRANSFER: ContentsSpec = {
  rule_id: "security_transfer_contents",
  document_type: "security_transfer",
  document_name: "security transfer of ownership (smlouva o zajišťovacím převodu vlastnického práva)",
  fields: [
    { key: "creditor", label: "SGEF as creditor (věřitel)" },
    { key: "debtor", label: "recipient as debtor (příjemce financování / dlužník)" },
    { key: "secured_contract", label: "secured loan agreement number (zajišťovaná smlouva)" },
    { key: "asset", label: "asset (předmět zajištění)" },
    { key: "serial_number", label: "asset serial number (výrobní číslo)" },
    { key: "asset_value", label: "asset value (hodnota)" },
    { key: "transfer_terms", label: "transfer of ownership and the terms of its duration and return" },
    { key: "date", label: "date of signing" },
  ],
  signatures: [SGEF, { role: "borrower", min: 1, label: "recipient" }],
};

export const INSURANCE_VINCULATION: ContentsSpec = {
  rule_id: "insurance_vinculation_contents",
  document_type: "insurance_vinculation",
  document_name: "insurance vinculation (prohlášení o vinkulaci pojištění)",
  fields: [
    { key: "policyholder", label: "policyholder (pojistník)" },
    { key: "insurer", label: "insurer (pojistitel)" },
    { key: "beneficiary", label: "SGEF as beneficiary (poskytovatel financování)" },
    { key: "insured_asset", label: "insured asset (předmět pojištění)" },
    { key: "policy_number", label: "policy number (číslo pojistné smlouvy)" },
    { key: "insured_amount", label: "scope or amount insured (rozsah, pojistná částka)" },
    { key: "benefit_clause", label: "commitment that benefits are paid to SGEF" },
    { key: "insurer_date", label: "insurer's date" },
  ],
  signatures: [{ role: "insurer", min: 1, label: "insurer" }],
};

export const GUARANTEE: ContentsSpec = {
  rule_id: "guarantee_contents",
  document_type: "guarantee",
  document_name: "guarantee declaration (prohlášení o ručení)",
  fields: [
    { key: "guarantor", label: "guarantor (ručitel)" },
    { key: "creditor", label: "SGEF as creditor (věřitel)" },
    { key: "debtor", label: "recipient as main debtor (příjemce financování)" },
    { key: "secured_contract", label: "secured contract or debt (zajištěná smlouva)" },
    { key: "scope", label: "scope of the guarantee (rozsah ručení)" },
    { key: "commitment", label: "guarantor's commitment to pay (závazek ručitele plnit)" },
    { key: "date", label: "date" },
  ],
  signatures: [{ role: "guarantor", min: 1, label: "guarantor" }, SGEF],
};
