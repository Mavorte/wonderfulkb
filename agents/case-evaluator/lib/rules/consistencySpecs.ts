// Entities compared across documents, from the control matrix
// (Hack_Seznam kontrol.xlsx). Each spec is one *_consistent rule; its evaluate
// tool is tools/evaluate_<rule_id>/.

import type { ConsistencySpec } from "./consistency";

// SGEF's own data, as its forms print it.
export const SGEF = {
  name: "SG Equipment Finance Czech Republic s.r.o.",
  ico: "61061344",
  dic: "CZ61061344",
  bank_account: "0162710187/0100",
};

export const RECIPIENT: ConsistencySpec = {
  rule_id: "recipient_consistent",
  entity: "recipient (příjemce financování)",
  attributes: [
    { key: "name", label: "name", kind: "text" },
    { key: "ico", label: "IČO", kind: "ico" },
    { key: "dic", label: "DIČ", kind: "dic" },
    { key: "address", label: "address (sídlo)", kind: "text" },
  ],
  reference: (run) =>
    run.client && {
      source: "the client record",
      values: { name: run.client.name, ico: run.client.ico, dic: run.client.dic, address: run.client.address },
    },
};

export const SUPPLIER: ConsistencySpec = {
  rule_id: "supplier_consistent",
  entity: "supplier (dodavatel)",
  attributes: [
    { key: "name", label: "name", kind: "text" },
    { key: "ico", label: "IČO", kind: "ico" },
    { key: "dic", label: "DIČ", kind: "dic" },
    { key: "address", label: "address (sídlo)", kind: "text" },
    { key: "bank_account", label: "bank account", kind: "account" },
  ],
};

export const PROVIDER: ConsistencySpec = {
  rule_id: "provider_consistent",
  entity: "provider (poskytovatel financování, SGEF)",
  attributes: [
    { key: "name", label: "name", kind: "text" },
    { key: "ico", label: "IČO", kind: "ico" },
    { key: "dic", label: "DIČ", kind: "dic" },
    { key: "bank_account", label: "bank account", kind: "account" },
  ],
  reference: () => ({ source: "SGEF's own data", values: SGEF }),
};

export const ASSET: ConsistencySpec = {
  rule_id: "asset_consistent",
  entity: "financed asset (předmět financování)",
  attributes: [
    { key: "name", label: "asset name", kind: "text" },
    { key: "manufacturer", label: "manufacturer", kind: "text" },
    { key: "serial_number", label: "serial number / VIN", kind: "id" },
    { key: "year", label: "year of manufacture", kind: "year" },
  ],
  reference: (run) => ({
    source: "the case record",
    values: { name: run.case_metadata.asset, serial_number: run.case_metadata.serial_number },
  }),
};

export const AMOUNTS: ConsistencySpec = {
  rule_id: "amounts_consistent",
  entity: "price and loan amount",
  attributes: [
    { key: "price", label: "price without VAT", kind: "amount" },
    { key: "vat", label: "VAT amount", kind: "amount" },
    { key: "price_with_vat", label: "price with VAT", kind: "amount" },
    { key: "loan_amount", label: "loan amount", kind: "amount" },
  ],
};

export const CONTRACT_NUMBER: ConsistencySpec = {
  rule_id: "contract_number_consistent",
  entity: "loan contract number",
  attributes: [{ key: "loan_number", label: "loan contract number", kind: "id" }],
  reference: (run) => ({ source: "the case record", values: { loan_number: run.case_metadata.loan_number } }),
};

export const GUARANTOR: ConsistencySpec = {
  rule_id: "guarantor_consistent",
  entity: "guarantor (ručitel)",
  attributes: [
    { key: "name", label: "name", kind: "text" },
    { key: "ico", label: "IČO", kind: "ico" },
    { key: "address", label: "address (sídlo)", kind: "text" },
  ],
  optional: true,
};
