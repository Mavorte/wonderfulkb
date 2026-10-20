import { describe, expect, it } from "vitest";
import { buildMultipart } from "./ingest";
import { type IntakeState, getNewFiles, getOutstanding, isPdf, toRequiredDocuments } from "./intake";

describe("required documents", () => {
  it("drops blanks and duplicates and keys the rest in order", () => {
    expect(toRequiredDocuments([" Faktura ", "", "Předávací protokol", "Faktura"])).toEqual([
      { key: "doc_1", name: "Faktura", attachment_ids: [] },
      { key: "doc_2", name: "Předávací protokol", attachment_ids: [] },
    ]);
  });

  it("lists only the requirements without an accepted upload", () => {
    const state: IntakeState = { required_documents: toRequiredDocuments(["Faktura", "Protokol"]), checked: {} };
    state.required_documents[0].attachment_ids.push("att-1");
    expect(getOutstanding(state)).toEqual(["Protokol"]);
  });
});

describe("files", () => {
  const files = [
    { id: "a", name: "smlouva.pdf", mimeType: "application/pdf", size: 1 },
    { id: "b", name: "foto.jpg", mimeType: "image/jpeg", size: 1 },
  ];

  it("skips files a tool already checked", () => {
    const state: IntakeState = {
      required_documents: [],
      checked: { a: { name: "smlouva.pdf", outcome: "loan_agreement", document_kind: "smlouva o úvěru" } },
    };
    expect(getNewFiles(state, files).map((f) => f.id)).toEqual(["b"]);
  });

  it("accepts PDFs by MIME type or extension", () => {
    expect(files.map(isPdf)).toEqual([true, false]);
    expect(isPdf({ id: "c", name: "Faktura.PDF", mimeType: "application/octet-stream", size: 1 })).toBe(true);
  });
});

describe("multipart body", () => {
  it("has one files part per document and the uploader", () => {
    const body = new TextDecoder().decode(
      buildMultipart("B", [{ name: 'a"b.pdf', data: new TextEncoder().encode("%PDF-1") }], "client@example.com"),
    );
    expect(body).toBe(
      '--B\r\nContent-Disposition: form-data; name="files"; filename="a_b.pdf"\r\nContent-Type: application/pdf\r\n\r\n%PDF-1\r\n' +
        '--B\r\nContent-Disposition: form-data; name="uploaded_by"\r\n\r\nclient@example.com\r\n--B--\r\n',
    );
  });
});
