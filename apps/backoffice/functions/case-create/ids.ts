// Mocked identifiers until the AWS case/client API creates real cases.

function getRandomBytes(length: number): Uint8Array {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return bytes;
}

/** Case id in the loan-number style of the existing intake links, e.g. `17026014-25`. */
export function generateCaseId(now: Date = new Date()): string {
  const digits = Array.from(getRandomBytes(8), (b) => String(b % 10)).join("");
  const year = String(now.getUTCFullYear() % 100).padStart(2, "0");
  return `${digits}-${year}`;
}

/** 128-bit random, base64url without padding (22 chars), the intake link `?h=` value. */
export function generateHash(): string {
  const binary = String.fromCharCode(...getRandomBytes(16));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
