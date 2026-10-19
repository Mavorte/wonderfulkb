export default function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{typeof value === "string" ? value : JSON.stringify(value, null, 2)}</pre>;
}
