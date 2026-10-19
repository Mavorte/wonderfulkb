export default function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("cs-CZ", { dateStyle: "medium", timeStyle: "short" });
}
