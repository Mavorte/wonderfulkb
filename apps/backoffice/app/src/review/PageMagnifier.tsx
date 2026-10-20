import { useEffect, useRef } from "react";

// Wide rather than tall, so a whole run of a text line fits.
const LENS_WIDTH = 480;
const LENS_HEIGHT = 220;
const ZOOM = 2;

/**
 * A rectangular lens that follows the mouse over its parent page and shows the page image enlarged.
 * It is fixed to the viewport so it can spill past the scrolling pages panel, and it ignores
 * pointer events, so the boxes on the page stay clickable through it.
 */
export default function PageMagnifier({ src }: { src: string }) {
  const lensRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const lens = lensRef.current;
    const page = lens?.parentElement;
    const img = page?.querySelector("img");
    if (!lens || !page || !img) return;

    // Styles are set directly: a re-render on every mouse move would be wasted work.
    const move = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      const rect = img.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      if (x < 0 || y < 0 || x > rect.width || y > rect.height) {
        lens.hidden = true;
        return;
      }
      // Centred on the cursor, but never past the right edge of the screen.
      const left = Math.min(e.clientX - LENS_WIDTH / 2, document.documentElement.clientWidth - LENS_WIDTH);
      const top = e.clientY - LENS_HEIGHT / 2;
      lens.hidden = false;
      lens.style.transform = `translate(${left}px, ${top}px)`;
      lens.style.backgroundSize = `${rect.width * ZOOM}px ${rect.height * ZOOM}px`;
      // The enlarged point under the cursor stays under the cursor, wherever the lens sits.
      lens.style.backgroundPosition = `${e.clientX - left - x * ZOOM}px ${e.clientY - top - y * ZOOM}px`;
    };
    const hide = () => {
      lens.hidden = true;
    };
    page.addEventListener("pointermove", move);
    page.addEventListener("pointerleave", hide);
    // The lens is fixed to the viewport, so scrolling the page under it would leave it stale.
    window.addEventListener("scroll", hide, true);
    return () => {
      page.removeEventListener("pointermove", move);
      page.removeEventListener("pointerleave", hide);
      window.removeEventListener("scroll", hide, true);
    };
  }, []);

  return (
    <div
      ref={lensRef}
      className="cr-lens"
      hidden
      aria-hidden="true"
      style={{ width: LENS_WIDTH, height: LENS_HEIGHT, backgroundImage: `url("${src}")` }}
    />
  );
}
