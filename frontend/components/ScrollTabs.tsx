"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// A row of tabs that stays inside its box. When there are more tabs than fit,
// the row slides sideways (swipe, trackpad, or the ‹ › arrows) and the
// selected tab (mark it with data-active="true") is kept in view.
export default function ScrollTabs({
  children,
  activeKey,
  label,
}: {
  children: React.ReactNode;
  activeKey?: string;
  label?: string;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(false);

  const update = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }, []);

  // re-check after every render (tabs can be added or removed) and on resize
  useEffect(() => {
    update();
  });

  useEffect(() => {
    const el = trackRef.current;
    window.addEventListener("resize", update);
    let observer: ResizeObserver | undefined;
    if (el && typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(update);
      observer.observe(el);
    }
    return () => {
      window.removeEventListener("resize", update);
      observer?.disconnect();
    };
  }, [update]);

  // keep the selected tab visible
  useEffect(() => {
    const el = trackRef.current;
    const active = el?.querySelector<HTMLElement>('[data-active="true"]');
    if (!el || !active) return;
    const start = active.offsetLeft;
    const end = start + active.offsetWidth;
    if (start < el.scrollLeft) {
      el.scrollTo({ left: Math.max(0, start - 8), behavior: "smooth" });
    } else if (end > el.scrollLeft + el.clientWidth) {
      el.scrollTo({ left: end - el.clientWidth + 8, behavior: "smooth" });
    }
  }, [activeKey]);

  const scrollByPage = (dir: 1 | -1) => {
    const el = trackRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * el.clientWidth * 0.7, behavior: "smooth" });
  };

  const arrowClass =
    "flex h-6 w-6 items-center justify-center rounded-full border border-slate-600 bg-slate-800 text-sm leading-none text-white transition hover:border-blue-500 hover:bg-slate-700";

  return (
    <div className="relative min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900">
      {canPrev && (
        <div className="pointer-events-none absolute inset-y-0 left-0 z-10 flex items-center rounded-l-lg bg-gradient-to-r from-slate-900 from-60% to-transparent pl-1 pr-4">
          <button
            type="button"
            onClick={() => scrollByPage(-1)}
            aria-label={label ? `Scroll ${label} left` : "Scroll left"}
            className={`${arrowClass} pointer-events-auto`}
          >
            ‹
          </button>
        </div>
      )}

      <div
        ref={trackRef}
        onScroll={update}
        role="group"
        aria-label={label}
        className="relative flex items-center gap-1.5 overflow-x-auto scroll-smooth p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        style={{ WebkitOverflowScrolling: "touch" }}
      >
        {children}
      </div>

      {canNext && (
        <div className="pointer-events-none absolute inset-y-0 right-0 z-10 flex items-center rounded-r-lg bg-gradient-to-l from-slate-900 from-60% to-transparent pl-4 pr-1">
          <button
            type="button"
            onClick={() => scrollByPage(1)}
            aria-label={label ? `Scroll ${label} right` : "Scroll right"}
            className={`${arrowClass} pointer-events-auto`}
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}
