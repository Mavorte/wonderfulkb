// The intake link hash the backoffice assigns; it never leaves Wonderful.

function getRandomBytes(length: number): Uint8Array {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return bytes;
}

/** 128-bit random, base64url without padding (22 chars), the intake link `?h=` value. */
export function generateHash(): string {
  const binary = String.fromCharCode(...getRandomBytes(16));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** The client's intake link, `<base>?h=<hash>`; null when either part is missing. */
export function buildIntakeLink(baseUrl: string, hash: string | null): string | null {
  const base = baseUrl.trim().replace(/\/+$/, "");
  return base && hash ? `${base}?h=${hash}` : null;
}
