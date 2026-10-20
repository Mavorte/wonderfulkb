import type { CSSProperties } from "react";

// A grey placeholder block. Callers wrap a whole skeleton layout in one aria-busy region with a label,
// so each block is hidden from assistive tech.
export default function Skeleton({ width, height, className }: { width?: CSSProperties["width"]; height?: CSSProperties["height"]; className?: string }) {
  return <span className={`bo-skeleton${className ? ` ${className}` : ""}`} style={{ width, height }} aria-hidden="true" />;
}
