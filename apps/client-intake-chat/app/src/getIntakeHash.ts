// The intake link carries the case hash as `?h=<hash>` on the app's anonymous
// share link (`/s/<code>?h=<hash>`).
export default function getIntakeHash(): string {
  return new URLSearchParams(window.location.search).get("h")?.trim() ?? "";
}
