"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";

export interface SeatItem {
  show_seat_id: string;
  row_label: string;
  seat_number: number;
  seat_type: string;
  status: "available" | "locked" | "booked" | "reserved" | "mine";
  price: number;
  x_pos?: number | null;
  y_pos?: number | null;
  section_name?: string | null;
  locked_by?: string;
}

export interface ZoneItem {
  id: string;
  name: string;
  zone_type: string;
  total_capacity: number;
  booked_count: number;
  locked_count: number;
  price: number;
  color_hex?: string;
  display_order?: number;
  polygon_coords?: [number, number][] | null;
  x_pos?: number | null;
  y_pos?: number | null;
  width?: number | null;
  height?: number | null;
  available_capacity: number;
}

interface VenueLayoutCanvasProps {
  layoutType: string;
  stagePosition: string;
  layoutConfig?: any;
  seats: SeatItem[];
  zones: ZoneItem[];
  selectedSeatIds: string[];
  selectedZoneId?: string | null;
  onToggleSeat: (seat: SeatItem) => void;
  onSelectZone: (zone: ZoneItem) => void;
}

export default function VenueLayoutCanvas({
  layoutType,
  stagePosition,
  layoutConfig,
  seats,
  zones,
  selectedSeatIds,
  selectedZoneId,
  onToggleSeat,
  onSelectZone,
}: VenueLayoutCanvasProps) {
  // Zoom and pan state
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [selectedSection, setSelectedSection] = useState<string>("all");

  // Stable hover & mobile tap inspection state
  const [activeInfo, setActiveInfo] = useState<{
    type: "seat" | "zone";
    data: SeatItem | ZoneItem;
  } | null>(null);

  // Floating tooltip position (clamped and non-intercepting)
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number } | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const dragOriginRef = useRef<{ clientX: number; clientY: number }>({ clientX: 0, clientY: 0 });
  const hasMovedRef = useRef<boolean>(false);
  const panRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const zoomRef = useRef<number>(1.0);
  const rafRef = useRef<number | null>(null);
  const touchDistanceRef = useRef<number | null>(null);
  const hasAutoFit = useRef(false);

  panRef.current = pan;
  zoomRef.current = zoom;

  // Group sections for filtering
  const sections = useMemo(() => {
    const set = new Set<string>();
    seats.forEach((s) => {
      if (s.section_name) set.add(s.section_name);
    });
    return Array.from(set);
  }, [seats]);

  // Determine if this is a concert with standing zones
  const isConcertWithZones = zones.length > 0 || layoutType === "concert";

  // Calculate coordinates with 100% strict vertical separation:
  // 1. Stage at top (y: 30 - 85)
  // 2. Standing zones (y: 115 - 325)
  // 3. Section divider ribbon (y: 345 - 370)
  // 4. Numbered seats (y: 395+)
  const {
    computedSeats,
    computedZones,
    contentWidth,
    contentHeight,
    rowGroups,
    stageY,
    stageW,
    dividerY,
  } = useMemo(() => {
    const seatSize = 34;
    const seatGap = 10;
    const aisleGap = 36;

    const rowLabels = Array.from(new Set(seats.map((s) => s.row_label))).sort();
    const rowIdxMap = new Map(rowLabels.map((lbl, idx) => [lbl, idx]));
    const maxSeatNum = Math.max(...seats.map((s) => s.seat_number), 1);
    const splitCol = Math.floor(maxSeatNum / 2);
    const hasAisle = maxSeatNum > 6;

    // Actual seat block width
    const seatBlockWidth =
      (maxSeatNum - 1) * (seatSize + seatGap) + (hasAisle ? aisleGap : 0) + seatSize;

    // Minimum comfortable canvas width
    const stageWidth = Math.max(seatBlockWidth * 1.15, 520);
    const calcWidth = Math.max(stageWidth + 180, seatBlockWidth + 220, 780);

    // Dynamic vertical staging
    const stY = 30;
    let nextY = 110;

    // 1. Position Standing Zones (VIP Fan Pit & General Standing)
    const calcZones = zones.map((zone, idx) => {
      const isFanPit = zone.zone_type === "fan_pit" || zone.name.toLowerCase().includes("fan pit") || idx === 0;
      const zoneW = isFanPit ? Math.min(calcWidth - 160, 520) : Math.min(calcWidth - 120, 580);
      const zoneH = isFanPit ? 88 : 94;
      const zoneX = (calcWidth - zoneW) / 2;
      const zoneY = nextY;

      nextY += zoneH + 20;

      return {
        ...zone,
        calcX: zoneX,
        calcY: zoneY,
        calcW: zoneW,
        calcH: zoneH,
        isFanPit,
      };
    });

    // 2. Section divider position
    const divY = zones.length > 0 ? nextY + 10 : 0;
    if (zones.length > 0) {
      nextY += 45;
    }

    // 3. Position Numbered Seats (Strictly below all standing areas!)
    const seatsStartX = (calcWidth - seatBlockWidth) / 2;
    const seatsStartY = nextY + 15;

    const calcSeats = seats.map((seat) => {
      let x = seat.x_pos;
      let y = seat.y_pos;

      // Always recalculate positions dynamically when standing zones are present to prevent any overlap
      if (x == null || y == null || zones.length > 0) {
        const rIdx = rowIdxMap.get(seat.row_label) ?? 0;
        const col = seat.seat_number;
        const colOffset =
          (col - 1) * (seatSize + seatGap) + (hasAisle && col > splitCol ? aisleGap : 0);

        x = seatsStartX + colOffset;
        y = seatsStartY + rIdx * 50;

        // Subtle curve for cinema/theatre (not flat concert grandstands)
        if ((layoutType === "cinema" || layoutType === "theatre") && zones.length === 0) {
          const centerCol = (maxSeatNum + 1) / 2;
          const distFromCenter = Math.abs(col - centerCol);
          y += Math.pow(distFromCenter / 2.7, 1.4);
        }
      }

      return {
        ...seat,
        calcX: Number(x),
        calcY: Number(y),
      };
    });

    // 4. Row groups for left/right row badges
    const map = new Map<
      string,
      { y: number; minX: number; maxX: number; tier: string; price: number }
    >();
    calcSeats.forEach((s) => {
      const existing = map.get(s.row_label);
      if (!existing) {
        map.set(s.row_label, {
          y: s.calcY,
          minX: s.calcX,
          maxX: s.calcX + seatSize,
          tier: s.seat_type,
          price: s.price,
        });
      } else {
        if (s.calcX < existing.minX) existing.minX = s.calcX;
        if (s.calcX + seatSize > existing.maxX) existing.maxX = s.calcX + seatSize;
        if (s.calcY < existing.y) existing.y = s.calcY;
      }
    });

    const rows = Array.from(map.entries()).map(([rowLabel, data]) => ({
      rowLabel,
      ...data,
    }));

    const finalY = seatsStartY + rowLabels.length * 50 + 60;

    return {
      computedSeats: calcSeats,
      computedZones: calcZones,
      contentWidth: calcWidth,
      contentHeight: Math.max(finalY, 520),
      rowGroups: rows,
      stageY: stY,
      stageW: stageWidth,
      dividerY: divY,
    };
  }, [seats, zones, layoutType]);

  // Fit to screen calculation: Centers layout and computes optimal scale factor
  const handleFitToScreen = useCallback(() => {
    if (!containerRef.current) return;
    const containerW = containerRef.current.clientWidth;
    const containerH = containerRef.current.clientHeight || 530;

    const pad = 36;
    const scaleX = (containerW - pad) / contentWidth;
    const scaleY = (containerH - pad) / contentHeight;
    const newScale = Math.min(Math.max(Math.min(scaleX, scaleY), 0.55), 1.5);

    const newPanX = (containerW - contentWidth * newScale) / 2;
    const newPanY = Math.max((containerH - contentHeight * newScale) / 2, 16);

    setZoom(Number(newScale.toFixed(2)));
    setPan({ x: Math.round(newPanX), y: Math.round(newPanY) });
  }, [contentWidth, contentHeight]);

  // Auto-fit on initial render
  useEffect(() => {
    if (!hasAutoFit.current && (seats.length > 0 || zones.length > 0)) {
      hasAutoFit.current = true;
      const timer = setTimeout(handleFitToScreen, 90);
      return () => clearTimeout(timer);
    }
  }, [seats.length, zones.length, handleFitToScreen]);

  // Reset View
  const handleResetView = useCallback(() => {
    setSelectedSection("all");
    handleFitToScreen();
  }, [handleFitToScreen]);

  // Zoom centered at mouse pointer (Figma / Google Maps standard UX)
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomDelta = e.deltaY < 0 ? 1.15 : 0.87;
    const newZoom = Math.min(Math.max(Number((zoomRef.current * zoomDelta).toFixed(3)), 0.5), 2.8);

    const newPanX = mouseX - (mouseX - panRef.current.x) * (newZoom / zoomRef.current);
    const newPanY = mouseY - (mouseY - panRef.current.y) * (newZoom / zoomRef.current);

    setZoom(newZoom);
    setPan({ x: newPanX, y: newPanY });
  };

  // Zoom In / Out buttons
  const handleButtonZoom = (factor: number) => {
    if (!containerRef.current) return;
    const containerW = containerRef.current.clientWidth;
    const containerH = containerRef.current.clientHeight;
    const centerX = containerW / 2;
    const centerY = containerH / 2;

    const newZoom = Math.min(Math.max(Number((zoom * factor).toFixed(2)), 0.5), 2.8);
    const newPanX = centerX - (centerX - pan.x) * (newZoom / zoom);
    const newPanY = centerY - (centerY - pan.y) * (newZoom / zoom);

    setZoom(newZoom);
    setPan({ x: newPanX, y: newPanY });
  };

  // Section drill down
  const handleSelectSection = useCallback(
    (secName: string) => {
      setSelectedSection(secName);
      if (secName === "all") {
        handleResetView();
        return;
      }

      const secSeats = computedSeats.filter((s) => s.section_name === secName);
      if (!secSeats.length || !containerRef.current) return;

      const xs = secSeats.map((s) => s.calcX);
      const ys = secSeats.map((s) => s.calcY);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs) + 34;
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys) + 34;

      const secW = maxX - minX;
      const secH = maxY - minY;
      const containerW = containerRef.current.clientWidth;
      const containerH = containerRef.current.clientHeight;

      const scale = Math.min(
        Math.max(Math.min((containerW - 80) / secW, (containerH - 80) / secH), 0.9),
        2.2
      );
      const targetPanX = containerW / 2 - (minX + secW / 2) * scale;
      const targetPanY = containerH / 2 - (minY + secH / 2) * scale;

      setZoom(Number(scale.toFixed(2)));
      setPan({ x: Math.round(targetPanX), y: Math.round(targetPanY) });
    },
    [computedSeats, handleResetView]
  );

  // Mouse pan handlers: Dragging engages only after > 4px movement on empty canvas
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    dragOriginRef.current = { clientX: e.clientX, clientY: e.clientY };
    hasMovedRef.current = false;
    dragStartRef.current = {
      x: e.clientX - panRef.current.x,
      y: e.clientY - panRef.current.y,
    };
    setIsDragging(true);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;

    const dx = Math.abs(e.clientX - dragOriginRef.current.clientX);
    const dy = Math.abs(e.clientY - dragOriginRef.current.clientY);

    // Only engage canvas pan if pointer moves more than 4 pixels
    if (dx > 4 || dy > 4) {
      hasMovedRef.current = true;
    }

    if (!hasMovedRef.current) return;

    const newX = e.clientX - dragStartRef.current.x;
    const newY = e.clientY - dragStartRef.current.y;

    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(() => {
      setPan({ x: newX, y: newY });
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    hasMovedRef.current = false;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  };

  // Touch handlers for mobile pan & pinch
  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length === 1) {
      hasMovedRef.current = false;
      dragOriginRef.current = { clientX: e.touches[0].clientX, clientY: e.touches[0].clientY };
      setIsDragging(true);
      dragStartRef.current = {
        x: e.touches[0].clientX - panRef.current.x,
        y: e.touches[0].clientY - panRef.current.y,
      };
    } else if (e.touches.length === 2) {
      touchDistanceRef.current = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    if (e.touches.length === 1 && isDragging) {
      const dx = Math.abs(e.touches[0].clientX - dragOriginRef.current.clientX);
      const dy = Math.abs(e.touches[0].clientY - dragOriginRef.current.clientY);
      if (dx > 4 || dy > 4) hasMovedRef.current = true;
      if (!hasMovedRef.current) return;

      const newX = e.touches[0].clientX - dragStartRef.current.x;
      const newY = e.touches[0].clientY - dragStartRef.current.y;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        setPan({ x: newX, y: newY });
      });
    } else if (e.touches.length === 2 && touchDistanceRef.current != null) {
      const currentDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const factor = currentDist / touchDistanceRef.current;
      setZoom((prev) => Math.min(Math.max(prev * factor, 0.5), 2.8));
      touchDistanceRef.current = currentDist;
    }
  };

  const handleTouchEnd = () => {
    setIsDragging(false);
    hasMovedRef.current = false;
    touchDistanceRef.current = null;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  };

  // Stable hover listeners: calculate stable anchored tooltip position without re-rendering on mousemove
  const handleSeatEnter = (seat: SeatItem) => {
    setActiveInfo({ type: "seat", data: seat });
    const sx = ((seat as any).calcX ?? 0) * zoomRef.current + panRef.current.x + 17;
    const sy = ((seat as any).calcY ?? 0) * zoomRef.current + panRef.current.y - 12;
    setTooltipPos({ x: sx, y: sy });
  };

  const handleZoneEnter = (zone: ZoneItem) => {
    setActiveInfo({ type: "zone", data: zone });
    const zx = (((zone as any).calcX ?? 0) + ((zone as any).calcW ?? 200) / 2) * zoomRef.current + panRef.current.x;
    const zy = ((zone as any).calcY ?? 0) * zoomRef.current + panRef.current.y - 12;
    setTooltipPos({ x: zx, y: zy });
  };

  // Only clear when pointer leaves canvas entirely
  const handleCanvasLeave = () => {
    handleMouseUp();
    setActiveInfo(null);
    setTooltipPos(null);
  };

  const isSeatInActiveSection = (seat: SeatItem) => {
    if (selectedSection === "all") return true;
    return seat.section_name === selectedSection;
  };

  return (
    <div className="relative w-full rounded-2xl border border-slate-800 bg-[#0c0f18] p-3 sm:p-5 shadow-2xl overflow-hidden select-none">
      {/* 1. Header Toolbar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
        {/* Section Filters */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 mr-1">
            Section:
          </span>
          <button
            type="button"
            onClick={() => handleSelectSection("all")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              selectedSection === "all"
                ? "bg-blue-600 text-white shadow-sm shadow-blue-500/50"
                : "bg-slate-800/80 text-slate-300 hover:bg-slate-700"
            }`}
          >
            All Sections
          </button>
          {sections.map((sec) => (
            <button
              key={sec}
              type="button"
              onClick={() => handleSelectSection(sec)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                selectedSection === sec
                  ? "bg-blue-600 text-white shadow-sm shadow-blue-500/50"
                  : "bg-slate-800/80 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {sec}
            </button>
          ))}
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1.5 rounded-xl border border-slate-700/80 bg-slate-900/90 p-1 text-xs shadow-inner">
          <button
            type="button"
            onClick={() => handleButtonZoom(0.85)}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800 font-bold text-slate-200 transition hover:bg-slate-700 active:scale-95"
            title="Zoom Out"
          >
            −
          </button>
          <span className="w-12 text-center font-mono text-[11px] text-slate-300 font-bold">
            {Math.round(zoom * 100)}%
          </span>
          <button
            type="button"
            onClick={() => handleButtonZoom(1.18)}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-800 font-bold text-slate-200 transition hover:bg-slate-700 active:scale-95"
            title="Zoom In"
          >
            +
          </button>
          <button
            type="button"
            onClick={handleFitToScreen}
            className="rounded-lg bg-slate-800 px-2.5 py-1 font-semibold text-slate-300 transition hover:bg-slate-700 active:scale-95"
            title="Fit to Screen"
          >
            Fit
          </button>
          <button
            type="button"
            onClick={handleResetView}
            className="rounded-lg bg-slate-800 px-2.5 py-1 font-semibold text-slate-300 transition hover:bg-slate-700 active:scale-95"
            title="Reset View"
          >
            Reset
          </button>
        </div>
      </div>

      {/* 2. Hardware-Accelerated Interactive Canvas Container */}
      <div
        ref={containerRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleCanvasLeave}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        className={`relative h-[550px] w-full overflow-hidden rounded-xl border border-slate-800/90 bg-[#080a10] ${
          isDragging ? "cursor-grabbing" : "cursor-grab"
        }`}
      >
        {/* Background Grid */}
        <div
          className="pointer-events-none absolute inset-0 opacity-35"
          style={{
            backgroundImage: "radial-gradient(#1e293b 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        />

        {/* Viewport Layer with Coordinated Transform */}
        <div
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "0 0",
            width: `${contentWidth}px`,
            height: `${contentHeight}px`,
            willChange: "transform",
            transition: isDragging ? "none" : "transform 0.08s ease-out",
          }}
          className="relative"
        >
          <svg
            width={contentWidth}
            height={contentHeight}
            viewBox={`0 0 ${contentWidth} ${contentHeight}`}
            className="overflow-visible"
          >
            <defs>
              <linearGradient id="concertNeonStage" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#ec4899" />
                <stop offset="50%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#3b82f6" />
              </linearGradient>

              <linearGradient id="cinemaScreenGlow" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#1e3a8a" />
                <stop offset="50%" stopColor="#60a5fa" />
                <stop offset="100%" stopColor="#1e3a8a" />
              </linearGradient>

              <linearGradient id="theatreArchGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#78350f" />
                <stop offset="50%" stopColor="#f59e0b" />
                <stop offset="100%" stopColor="#78350f" />
              </linearGradient>

              <linearGradient id="screenBeam" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* 3. MAIN LIVE STAGE (Distinct, Separated, Clear). The backend picks layoutType
                from the event type: only movies get "cinema" (a screen), live events a stage. */}
            {stagePosition === "center" && layoutType !== "cinema" ? (
              // 360° Arena Center Stage
              <g transform={`translate(${contentWidth / 2}, 160)`}>
                <circle r="75" fill="#1e1b4b" stroke="#818cf8" strokeWidth="2.5" />
                <circle r="48" fill="#0f172a" stroke="#6366f1" strokeWidth="1.5" />
                <text
                  x="0"
                  y="-4"
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="12"
                  fontWeight="900"
                  letterSpacing="2"
                >
                  360° ARENA STAGE
                </text>
                <text x="0" y="14" textAnchor="middle" fill="#a5b4fc" fontSize="9.5" fontWeight="700">
                  IN-THE-ROUND
                </text>
              </g>
            ) : layoutType === "concert" ? (
              // Live Concert Main Stage with Sound PA Wings
              <g transform={`translate(${contentWidth / 2 - stageW / 2}, ${stageY})`}>
                {/* Main Stage Rectangle */}
                <rect
                  x="0"
                  y="0"
                  width={stageW}
                  height="54"
                  rx="10"
                  fill="url(#concertNeonStage)"
                  stroke="#ffffff"
                  strokeWidth="1.5"
                  strokeOpacity="0.4"
                  filter="drop-shadow(0px 0px 18px rgba(236, 72, 153, 0.4))"
                />
                <text
                  x={stageW / 2}
                  y="33"
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="13.5"
                  fontWeight="900"
                  letterSpacing="3.5"
                >
                  🎤 MAIN LIVE CONCERT STAGE 🎸
                </text>

                {/* Left PA Speaker Tower */}
                <rect x="-38" y="5" width="28" height="44" rx="5" fill="#1e293b" stroke="#ec4899" strokeWidth="1.5" />
                <text x="-24" y="31" textAnchor="middle" fill="#ec4899" fontSize="8.5" fontWeight="800">PA</text>

                {/* Right PA Speaker Tower */}
                <rect x={stageW + 10} y="5" width="28" height="44" rx="5" fill="#1e293b" stroke="#ec4899" strokeWidth="1.5" />
                <text x={stageW + 24} y="31" textAnchor="middle" fill="#ec4899" fontSize="8.5" fontWeight="800">PA</text>
              </g>
            ) : layoutType === "theatre" ? (
              // Theatre Proscenium Stage
              <g transform={`translate(${contentWidth / 2 - stageW / 2}, ${stageY})`}>
                <rect
                  x="0"
                  y="0"
                  width={stageW}
                  height="50"
                  rx="8"
                  fill="url(#theatreArchGrad)"
                  stroke="#fbbf24"
                  strokeWidth="2"
                  filter="drop-shadow(0px 0px 12px rgba(251, 191, 36, 0.3))"
                />
                <text
                  x={stageW / 2}
                  y="31"
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="12.5"
                  fontWeight="800"
                  letterSpacing="2.5"
                >
                  🎭 PROSCENIUM THEATRE STAGE 🎭
                </text>
              </g>
            ) : layoutType === "stage" ? (
              // Plain stage for comedy and other live events
              <g transform={`translate(${contentWidth / 2 - stageW / 2}, ${stageY})`}>
                <rect
                  x="0"
                  y="0"
                  width={stageW}
                  height="50"
                  rx="8"
                  fill="#1e293b"
                  stroke="#a78bfa"
                  strokeWidth="2"
                  filter="drop-shadow(0px 0px 12px rgba(167, 139, 250, 0.3))"
                />
                <text
                  x={stageW / 2}
                  y="31"
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="12.5"
                  fontWeight="800"
                  letterSpacing="3"
                >
                  🎤 STAGE
                </text>
              </g>
            ) : (
              // Cinema Curved Screen (movies only)
              <g transform={`translate(${contentWidth / 2 - stageW / 2}, ${stageY})`}>
                <polygon
                  points={`20,32 ${stageW - 20},32 ${stageW + 20},160 -20,160`}
                  fill="url(#screenBeam)"
                />
                <path
                  d={`M 10 32 Q ${stageW / 2} 4 ${stageW - 10} 32`}
                  fill="none"
                  stroke="url(#cinemaScreenGlow)"
                  strokeWidth="6"
                  strokeLinecap="round"
                  filter="drop-shadow(0px 0px 14px rgba(96, 165, 250, 0.6))"
                />
                <text
                  x={stageW / 2}
                  y="52"
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize="10.5"
                  fontWeight="800"
                  letterSpacing="4"
                >
                  SCREEN THIS WAY (ALL EYES THIS WAY)
                </text>
              </g>
            )}

            {/* 4. STANDING ADMISSION ZONES (NO NUMBERED SEATS INSIDE!) */}
            {computedZones.map((zone) => {
              const isSelected = selectedZoneId === zone.id;
              const isFanPit = zone.isFanPit;
              const borderColor = isFanPit ? "#ff0055" : (zone.color_hex || "#3b82f6");
              const bgFill = isSelected
                ? "#1e293b"
                : isFanPit
                ? "#190812"
                : "#0a1324";

              return (
                <g
                  key={zone.id}
                  transform={`translate(${zone.calcX}, ${zone.calcY})`}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectZone(zone);
                  }}
                  onMouseEnter={() => handleZoneEnter(zone)}
                  className="cursor-pointer transition-transform hover:opacity-95"
                >
                  {/* Outer Section Boundary */}
                  <rect
                    x="0"
                    y="0"
                    width={zone.calcW}
                    height={zone.calcH}
                    rx="12"
                    fill={bgFill}
                    stroke={isSelected ? "#38bdf8" : borderColor}
                    strokeWidth={isSelected ? "3" : "1.8"}
                    strokeDasharray={isFanPit ? "none" : "6,3"}
                    filter={isSelected ? "drop-shadow(0px 0px 14px rgba(56, 189, 248, 0.6))" : undefined}
                  />

                  {/* Standing Zone Badge & Icon */}
                  <text
                    x="20"
                    y="28"
                    fill="#ffffff"
                    fontSize="13"
                    fontWeight="800"
                    letterSpacing="0.8"
                  >
                    {isFanPit ? "👑 VIP FAN PIT (FRONT OF STAGE)" : "🎫 GENERAL STANDING LAWN"}
                  </text>

                  {/* Subtitle / Admission Info */}
                  <text x="20" y="50" fill="#94a3b8" fontSize="10.5" fontWeight="500">
                    {isFanPit
                      ? "⚡ Unreserved Standing Admission • Directly in front of stage"
                      : "⚡ General Admission Standing Grounds • Open Lawn Area"}
                  </text>

                  {/* Capacity Pill */}
                  <rect
                    x="20"
                    y="60"
                    width="180"
                    height="20"
                    rx="5"
                    fill="#0f172a"
                    stroke="#334155"
                    strokeWidth="1"
                  />
                  <text x="30" y="74" fill="#38bdf8" fontSize="9.5" fontWeight="700">
                    ● {zone.available_capacity} / {zone.total_capacity} Passes Available
                  </text>

                  {/* Price Badge Button (Right Flank) */}
                  <rect
                    x={zone.calcW - 130}
                    y="24"
                    width="114"
                    height="40"
                    rx="8"
                    fill={isSelected ? "#2563eb" : "#1e293b"}
                    stroke={isSelected ? "#60a5fa" : "#334155"}
                    strokeWidth="1"
                  />
                  <text
                    x={zone.calcW - 73}
                    y="42"
                    textAnchor="middle"
                    fill={isSelected ? "#ffffff" : "#34d399"}
                    fontSize="13.5"
                    fontWeight="900"
                  >
                    ₹{zone.price}
                  </text>
                  <text
                    x={zone.calcW - 73}
                    y="56"
                    textAnchor="middle"
                    fill={isSelected ? "#dbeafe" : "#94a3b8"}
                    fontSize="8.5"
                    fontWeight="600"
                  >
                    {isSelected ? "✓ SELECTED" : "SELECT PASS"}
                  </text>
                </g>
              );
            })}

            {/* 5. CLEAR SECTION DIVIDER (BETWEEN STANDING AND ASSIGNED SEATING) */}
            {dividerY > 0 && (
              <g transform={`translate(${contentWidth / 2}, ${dividerY})`}>
                <line
                  x1="-240"
                  y1="0"
                  x2="240"
                  y2="0"
                  stroke="#334155"
                  strokeWidth="1"
                  strokeDasharray="4,4"
                />
                <rect
                  x="-180"
                  y="-12"
                  width="360"
                  height="24"
                  rx="6"
                  fill="#0c0f18"
                  stroke="#475569"
                  strokeWidth="1"
                />
                <text
                  x="0"
                  y="4"
                  textAnchor="middle"
                  fill="#e2e8f0"
                  fontSize="10"
                  fontWeight="800"
                  letterSpacing="1.5"
                >
                  💺 RESERVED GRANDSTAND SEATING (ASSIGNED SEATS)
                </text>
              </g>
            )}

            {/* 6. NUMBERED SEATS (STRICTLY ASSIGNED SEATING AREA) */}
            {computedSeats.map((seat) => {
              const isSelected = selectedSeatIds.includes(seat.show_seat_id);
              const isMine = seat.status === "mine" || isSelected;
              const isBooked = seat.status === "booked";
              const isLocked = seat.status === "locked" && !isMine;
              const isAvailable = seat.status === "available" || isMine;
              const isPremium = seat.seat_type === "premium";
              const isAccessible = seat.seat_type === "accessible";
              const inActiveSection = isSeatInActiveSection(seat);

              // Colors
              let fill = "#062215";
              let stroke = "#10b981";
              let textColor = "#34d399";

              if (isMine) {
                fill = "#1d4ed8";
                stroke = "#60a5fa";
                textColor = "#ffffff";
              } else if (isBooked) {
                fill = "#181e2b";
                stroke = "#334155";
                textColor = "#475569";
              } else if (isLocked) {
                fill = "#2a1c07";
                stroke = "#d97706";
                textColor = "#fbbf24";
              } else if (isPremium) {
                fill = "#2a1b05";
                stroke = "#f59e0b";
                textColor = "#fcd34d";
              } else if (isAccessible) {
                fill = "#082f49";
                stroke = "#0ea5e9";
                textColor = "#38bdf8";
              }

              const isHovered =
                activeInfo?.type === "seat" &&
                (activeInfo.data as SeatItem).show_seat_id === seat.show_seat_id;

              return (
                <g
                  key={seat.show_seat_id}
                  transform={`translate(${seat.calcX}, ${seat.calcY})`}
                  onMouseDown={(e) => e.stopPropagation()}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (isAvailable) onToggleSeat(seat);
                  }}
                  onMouseEnter={() => handleSeatEnter(seat)}
                  className={
                    isAvailable
                      ? "cursor-pointer transition-opacity duration-100 hover:opacity-90"
                      : "cursor-not-allowed opacity-50"
                  }
                  opacity={inActiveSection ? 1 : 0.25}
                >
                  {/* Selected or Hovered glowing ring (zero layout shift) */}
                  {(isMine || isHovered) && (
                    <rect
                      x="-3"
                      y="-3"
                      width="40"
                      height="40"
                      rx="9"
                      fill="none"
                      stroke={isMine ? "#60a5fa" : "#38bdf8"}
                      strokeWidth={isMine ? "2" : "1.5"}
                      strokeDasharray={isMine ? "none" : "3,2"}
                      opacity="0.9"
                      pointerEvents="none"
                    />
                  )}

                  {/* Seat Cushion Body */}
                  <rect
                    x="0"
                    y="0"
                    width="34"
                    height="34"
                    rx="7"
                    fill={fill}
                    stroke={isHovered ? "#38bdf8" : stroke}
                    strokeWidth={isMine || isHovered ? "2" : "1.2"}
                  />

                  {/* Headrest Contour Line */}
                  <path
                    d="M 5 6 L 29 6"
                    stroke={isHovered ? "#38bdf8" : stroke}
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    opacity="0.6"
                    pointerEvents="none"
                  />

                  {/* Seat Number */}
                  {isAccessible ? (
                    <text
                      x="17"
                      y="23"
                      textAnchor="middle"
                      fill={textColor}
                      fontSize="13"
                      fontWeight="700"
                      pointerEvents="none"
                    >
                      ♿
                    </text>
                  ) : (
                    <text
                      x="17"
                      y="22"
                      textAnchor="middle"
                      fill={textColor}
                      fontSize="10.5"
                      fontWeight="800"
                      pointerEvents="none"
                    >
                      {seat.seat_number}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Left and Right Row Letter Badges (Clear Outside Clearance) */}
            {rowGroups.map(({ rowLabel, y, minX, maxX }) => {
              const inSection =
                selectedSection === "all" ||
                computedSeats.some(
                  (s) => s.row_label === rowLabel && s.section_name === selectedSection
                );

              return (
                <g key={`lbl-${rowLabel}`} opacity={inSection ? 0.9 : 0.2}>
                  {/* Left row badge */}
                  <rect
                    x={minX - 38}
                    y={y + 5}
                    width="24"
                    height="24"
                    rx="5"
                    fill="#1e293b"
                    stroke="#334155"
                    strokeWidth="1"
                  />
                  <text
                    x={minX - 26}
                    y={y + 21}
                    textAnchor="middle"
                    fill="#e2e8f0"
                    fontSize="11"
                    fontWeight="800"
                  >
                    {rowLabel}
                  </text>

                  {/* Right row badge */}
                  <rect
                    x={maxX + 14}
                    y={y + 5}
                    width="24"
                    height="24"
                    rx="5"
                    fill="#1e293b"
                    stroke="#334155"
                    strokeWidth="1"
                  />
                  <text
                    x={maxX + 26}
                    y={y + 21}
                    textAnchor="middle"
                    fill="#e2e8f0"
                    fontSize="11"
                    fontWeight="800"
                  >
                    {rowLabel}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* 8. Dedicated Real-Time Information HUD (Complete, Stable, Never Flickers) */}
      <div className="mt-2.5 flex items-center justify-between rounded-xl border border-slate-800/80 bg-slate-900/80 px-4 py-2.5 text-xs">
        {activeInfo?.type === "seat" ? (
          (() => {
            const seat = activeInfo.data as SeatItem;
            const isMine = selectedSeatIds.includes(seat.show_seat_id);
            return (
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-bold text-white text-sm">
                  {seat.section_name || "Grandstand"} • Row {seat.row_label}, Seat {seat.seat_number}
                </span>
                <span className="text-slate-500">•</span>
                <span className="text-slate-300 capitalize">{seat.seat_type} Tier</span>
                <span className="text-slate-500">•</span>
                <span className="font-extrabold text-emerald-400 text-sm">₹{seat.price}</span>
                <span className="text-slate-500">•</span>
                <span
                  className={`font-semibold ${
                    isMine
                      ? "text-blue-400"
                      : seat.status === "available"
                      ? "text-emerald-400"
                      : "text-amber-400"
                  }`}
                >
                  {isMine
                    ? "✓ Selected (Click to deselect)"
                    : seat.status === "available"
                    ? "● Available (Click to select)"
                    : seat.status === "booked"
                    ? "✕ Sold Out"
                    : "🔒 Locked by another user"}
                </span>
              </div>
            );
          })()
        ) : activeInfo?.type === "zone" ? (
          (() => {
            const zone = activeInfo.data as ZoneItem;
            return (
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="h-2 w-2 rounded-full bg-purple-400" />
                <span className="font-bold text-white text-sm">{zone.name}</span>
                <span className="text-slate-500">•</span>
                <span className="text-slate-300 capitalize">
                  {zone.zone_type === "fan_pit" ? "Front Fan Pit" : "General Standing"}
                </span>
                <span className="text-slate-500">•</span>
                <span className="font-extrabold text-emerald-400 text-sm">₹{zone.price}</span>
                <span className="text-slate-500">•</span>
                <span className="text-sky-300 font-medium">
                  {zone.available_capacity} of {zone.total_capacity} passes left
                </span>
                <span className="text-slate-500">•</span>
                <span className="text-blue-400 font-semibold">
                  {selectedZoneId === zone.id ? "✓ Selected (Select qty below)" : "Click to select pass"}
                </span>
              </div>
            );
          })()
        ) : (
          <div className="flex items-center gap-2 text-slate-400">
            <span>💡 Click any available seat or standing pass to select</span>
            <span>•</span>
            <span>Scroll or pinch to zoom</span>
            <span>•</span>
            <span>Drag to pan across the venue</span>
          </div>
        )}

        <div className="hidden md:flex items-center gap-2 text-slate-400 text-[11px]">
          <span>
            Selected: <strong className="text-white">{selectedSeatIds.length}</strong> seats
          </span>
        </div>
      </div>

      {/* 9. Clear Visual Legend */}
      <div className="mt-3 flex flex-wrap items-center justify-center gap-4 border-t border-slate-800/80 pt-3 text-xs text-slate-300">
        <div className="flex items-center gap-1.5">
          <div className="h-3.5 w-3.5 rounded border border-emerald-500 bg-[#062215]" />
          <span>Available</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-3.5 w-3.5 rounded border border-amber-500 bg-[#2a1b05]" />
          <span>Premium Tier</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-3.5 w-3.5 rounded border border-sky-500 bg-[#082f49]" />
          <span>♿ Accessible</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-3.5 w-3.5 rounded border border-blue-400 bg-blue-600 shadow-sm shadow-blue-500/50" />
          <span>Selected</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-3.5 w-3.5 rounded border border-amber-600 bg-[#2a1c07]" />
          <span>Held by Other</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-3.5 w-3.5 rounded border border-slate-600 bg-[#181e2b]" />
          <span>Sold Out</span>
        </div>
        {zones.length > 0 && (
          <>
            <div className="flex items-center gap-1.5">
              <div className="h-3.5 w-3.5 rounded border border-[#ff0055] bg-[#190812]" />
              <span>VIP Fan Pit</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-3.5 w-3.5 rounded border border-dashed border-blue-400 bg-[#0a1324]" />
              <span>General Standing</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

