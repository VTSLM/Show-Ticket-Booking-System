"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// A row that scrolls sideways: swipe on touch screens, drag with the mouse,
// or use the arrow buttons. Cards snap into place.
export default function ShowCarousel({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(false);
  const drag = useRef({ down: false, startX: 0, startLeft: 0, moved: false });

  const update = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  useEffect(() => {
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [update, count]);

  const scrollByPage = (dir: 1 | -1) => {
    const el = trackRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * el.clientWidth * 0.85, behavior: "smooth" });
  };

  // mouse drag (touch uses the browser's own swipe scrolling)
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse") return;
    const el = trackRef.current;
    if (!el) return;
    drag.current = { down: true, startX: e.clientX, startLeft: el.scrollLeft, moved: false };
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    const el = trackRef.current;
    if (!d.down || !el) return;
    const dx = e.clientX - d.startX;
    if (Math.abs(dx) > 5) d.moved = true;
    if (d.moved) {
      el.style.scrollSnapType = "none";
      el.scrollLeft = d.startLeft - dx;
    }
  };
  const endDrag = () => {
    const el = trackRef.current;
    drag.current.down = false;
    if (el) el.style.scrollSnapType = "";
  };
  // a drag must not open the card that is under the mouse
  const onClickCapture = (e: React.MouseEvent) => {
    if (drag.current.moved) {
      e.preventDefault();
      e.stopPropagation();
      drag.current.moved = false;
    }
  };

  return (
    <section className="mb-10" aria-label={title}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-white">
          {title} <span className="text-sm font-normal text-slate-400">({count})</span>
        </h2>
        <div className="hidden gap-2 sm:flex">
          <button
            type="button"
            onClick={() => scrollByPage(-1)}
            disabled={!canPrev}
            aria-label={`Scroll ${title} left`}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-lg text-white transition hover:border-blue-500 disabled:opacity-30"
          >
            ‹
          </button>
          <button
            type="button"
            onClick={() => scrollByPage(1)}
            disabled={!canNext}
            aria-label={`Scroll ${title} right`}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-lg text-white transition hover:border-blue-500 disabled:opacity-30"
          >
            ›
          </button>
        </div>
      </div>

      <div
        ref={trackRef}
        onScroll={update}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerLeave={endDrag}
        onClickCapture={onClickCapture}
        className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth px-4 pb-3 sm:mx-0 sm:px-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
        {children}
      </div>
    </section>
  );
}
