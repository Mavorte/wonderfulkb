// The intake link carries the case hash as `?h=<hash>` next to the platform's
// own `access_token`.
export default function getIntakeHash(): string {
  return new URLSearchParams(window.location.search).get("h")?.trim() ?? "";
}
