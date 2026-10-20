// Single-colour 24px icons in the KB style; fill follows `currentColor` or a
// `.kb-icon--*` role class.
const PATHS = {
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm4 18H6V4h7v5h5v11ZM8 13h8v2H8v-2Zm0 4h8v2H8v-2Z",
  upload: "M11 16V7.83l-3.59 3.58L6 10l6-6 6 6-1.41 1.41L13 7.83V16h-2Zm-6 2h14v2H5v-2Z",
  check: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-1.5 14.5-4-4 1.41-1.41 2.59 2.58 5.59-5.58L17.5 9.5l-7 7Z",
  close: "M18.3 7.11 16.89 5.7 12 10.59 7.11 5.7 5.7 7.11 10.59 12 5.7 16.89l1.41 1.41L12 13.41l4.89 4.89 1.41-1.41L13.41 12l4.89-4.89Z",
  info: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 15h-2v-6h2v6Zm0-8h-2V7h2v2Z",
} as const;

export type KbIconName = keyof typeof PATHS;

export default function KbIcon({ name, className = "" }: { name: KbIconName; className?: string }) {
  return (
    <svg className={`kb-icon ${className}`} viewBox="0 0 24 24" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}
