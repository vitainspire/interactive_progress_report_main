import { useEffect, useRef, useState } from "react";
import { FitScreenIcon, ZoomInIcon, ZoomOutIcon } from "./Icons";

// The printable report card is a fixed 210mm-wide A4 page (~794px) — on a
// desktop-width preview column that's narrower than the container, so a
// flat 100% zoom happens to look right. On a phone it's far wider than the
// screen, so the "fit" zoom has to be computed from the container's actual
// width, not hardcoded to 1, or the report renders cut off/unreadable.
const A4_WIDTH_PX = 794;
const IFRAME_HEIGHT_PX = 1100;

export function ReportPreview({ reportUrl, iframeRef }: { reportUrl: string; iframeRef: React.RefObject<HTMLIFrameElement | null> }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const autoFit = useRef(true);

  const computeFit = () => {
    const el = containerRef.current;
    if (!el) return 1;
    const available = el.clientWidth - 48; // minus the container's own p-6 padding
    return Math.max(0.25, Math.min(1, available / A4_WIDTH_PX));
  };

  useEffect(() => {
    function applyFit() {
      if (autoFit.current) setZoom(computeFit());
    }
    applyFit();
    window.addEventListener("resize", applyFit);
    return () => window.removeEventListener("resize", applyFit);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function fitToScreen() {
    autoFit.current = true;
    setZoom(computeFit());
  }
  function zoomBy(delta: number) {
    autoFit.current = false;
    setZoom((z) => Math.max(0.25, Math.min(1.5, +(z + delta).toFixed(2))));
  }

  return (
    <div className="relative">
      <div ref={containerRef} className="dot-grid-plane overflow-auto rounded-md p-6" style={{ maxHeight: 900, background: "var(--page-plane)" }}>
        {/* Outer box is sized to the ACTUAL scaled-down footprint (not a
            percentage), so centering/layout treats it as a normal box
            instead of one that's 1/zoom times too wide for its parent —
            that mismatch is what let the card render shrunk but shoved to
            one side instead of centered on narrow screens. */}
        <div
          className="mx-auto overflow-hidden rounded-lg"
          style={{ width: A4_WIDTH_PX * zoom, height: IFRAME_HEIGHT_PX * zoom, boxShadow: "var(--shadow-pop)" }}
        >
          <div style={{ width: A4_WIDTH_PX, transform: `scale(${zoom})`, transformOrigin: "top left" }}>
            <iframe
              key={reportUrl}
              ref={iframeRef}
              src={reportUrl}
              title="Report card preview"
              className="border-0"
              style={{ width: A4_WIDTH_PX, height: IFRAME_HEIGHT_PX }}
            />
          </div>
        </div>
      </div>
      <div className="soft-card absolute bottom-4 right-4 flex items-center gap-1 p-1">
        <button
          onClick={() => zoomBy(-0.1)}
          aria-label="Zoom out"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-soft)]"
          style={{ color: "var(--text-secondary)" }}
        >
          <ZoomOutIcon size={15} />
        </button>
        <button
          onClick={fitToScreen}
          aria-label="Fit page"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-soft)]"
          style={{ color: "var(--text-secondary)" }}
        >
          <FitScreenIcon size={15} />
        </button>
        <button
          onClick={() => zoomBy(0.1)}
          aria-label="Zoom in"
          className="flex h-8 w-8 items-center justify-center rounded-full transition-colors duration-200 hover:bg-[var(--accent-soft)]"
          style={{ color: "var(--text-secondary)" }}
        >
          <ZoomInIcon size={15} />
        </button>
      </div>
    </div>
  );
}
