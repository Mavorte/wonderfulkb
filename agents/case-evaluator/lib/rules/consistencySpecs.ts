// Entities compared across documents, from the control matrix
// (Hack_Seznam kontrol.xlsx). Each spec is one *_consistent rule; its evaluate
// tool is tools/evaluate_<rule_id>/.

import type { ConsistencySpec } from "./consistency";

export const RECIPIENT: ConsistencySpec = {
  rule_id: "recipient_consistent",
  regions: { labels: ["smluvni_strana"], parties: ["borrower", "buyer"] },
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
  regions: { labels: ["smluvni_strana"], parties: ["supplier"] },
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
  regions: { labels: ["smluvni_strana"], parties: ["provider"] },
  entity: "provider (poskytovatel financování)",
  attributes: [
    { key: "name", label: "name", kind: "text" },
    { key: "ico", label: "IČO", kind: "ico" },
    { key: "dic", label: "DIČ", kind: "dic" },
    { key: "bank_account", label: "bank account", kind: "account" },
  ],
};

export const ASSET: ConsistencySpec = {
  rule_id: "asset_consistent",
  regions: { labels: ["predmet", "predani", "zajisteni"] },
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
  regions: { labels: ["cena_platba"] },
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
  regions: { labels: ["hlavicka", "odkaz_na_dokument", "zajisteni"] },
  entity: "loan contract number",
  attributes: [{ key: "loan_number", label: "loan contract number", kind: "id" }],
  reference: (run) => ({ source: "the case record", values: { loan_number: run.case_metadata.loan_number } }),
};

export const GUARANTOR: ConsistencySpec = {
  rule_id: "guarantor_consistent",
  regions: { labels: ["smluvni_strana", "zajisteni"], parties: ["guarantor"] },
  entity: "guarantor (ručitel)",
  attributes: [
    { key: "name", label: "name", kind: "text" },
    { key: "ico", label: "IČO", kind: "ico" },
    { key: "address", label: "address (sídlo)", kind: "text" },
  ],
  optional: true,
};
