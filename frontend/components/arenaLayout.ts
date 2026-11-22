// Geometry for concert arena / stadium seat maps (#198).
//
// Front (or end) stage: the stage sits at the top, the standing floor fans out in front of
// it as half rings (Fan Pit closest), and the numbered seats wrap round it as a horseshoe.
// Center stage: the stage sits in the middle, the floor rings surround it, and the seats
// form a full bowl with an entry aisle at the top.
//
// Rows are tiers: row A is the closest ring and each later row sits one step further out.
// Seat numbers run left to right as seen from the seats, split into blocks by aisles, and
// every row uses the same angles so seats line up radially like a real stand.

export const SEAT = 34;
const ROW_PITCH = 46; // distance between tiers
const MIN_SEAT_SPACING = 44; // along the innermost tier
const AISLE_UNITS = 1.4; // aisle width, in seat widths
const FRONT_SPAN = 210; // degrees of the horseshoe, centred straight below the stage
const ENTRY_UNITS = 6; // width of the entry aisle of a center-stage bowl, in seat widths
const PAD = 60;
const SIDE_LABEL_ROOM = 170; // room for section names to the left of a horseshoe

const BAND_COLORS = ["#6366f1", "#14b8a6", "#0ea5e9", "#a855f7", "#f43f5e"];
const PREMIUM_COLOR = "#f59e0b";

export interface ArenaSeatInput {
  show_seat_id: string;
  row_label: string;
  seat_number: number;
  seat_type: string;
  section_name?: string | null;
}

export interface ArenaZoneInput {
  id: string;
  name: string;
  zone_type: string;
  display_order?: number;
}

export interface ArenaBand {
  name: string;
  color: string;
  rIn: number;
  rOut: number;
}

export interface ArenaRing {
  id: string;
  isFanPit: boolean;
  rIn: number;
  rOut: number;
  labelX: number;
  labelY: number;
}

export interface ArenaGeometry {
  center: boolean;
  cx: number;
  cy: number;
  a0: number; // seating arc, degrees (SVG: 0 = right, 90 = down)
  a1: number;
  stageW: number;
  stageR: number;
  width: number;
  height: number;
  seats: Map<string, { x: number; y: number; rotate: number }>;
  bands: ArenaBand[];
  rings: ArenaRing[];
  rowLabels: { label: string; x: number; y: number }[];
  sectionLabels: { text: string; x: number; y: number; anchor: "end" | "middle"; color: string }[];
}

const rad = (deg: number) => (deg * Math.PI) / 180;
const naturalSort = (a: string, b: string) =>
  a.length - b.length || a.localeCompare(b, undefined, { numeric: true });

export function isFanPitZone(zone: ArenaZoneInput): boolean {
  return zone.zone_type === "fan_pit" || zone.name.toLowerCase().includes("fan pit");
}

export function computeArena(
  seats: ArenaSeatInput[],
  zones: ArenaZoneInput[],
  stagePosition: string
): ArenaGeometry {
  const center = stagePosition === "center";

  // Floor: Fan Pit closest to the stage, then the other standing zones
  const orderedZones = [...zones].sort(
    (a, b) =>
      Number(isFanPitZone(b)) - Number(isFanPitZone(a)) ||
      (a.display_order ?? 0) - (b.display_order ?? 0)
  );
  const stageR = 75;
  const ringWidth = 100;
  const floorStart = center ? stageR + 14 : 0; // front: the Fan Pit is a half disc under the stage
  const floorEnd = floorStart + Math.max(orderedZones.length * ringWidth, center ? 40 : 130);

  // Tiers and seat columns
  const rows = Array.from(new Set(seats.map((s) => s.row_label))).sort(naturalSort);
  const rowIdx = new Map(rows.map((r, i) => [r, i]));
  const maxSeat = Math.max(1, ...seats.map((s) => s.seat_number));
  const blocks = Math.min(8, Math.max(center ? 4 : 2, Math.round(maxSeat / (center ? 5 : 6))));
  const perBlock = Math.ceil(maxSeat / blocks);
  const usedBlocks = Math.ceil(maxSeat / perBlock);
  const units = maxSeat + (usedBlocks - 1) * AISLE_UNITS + (center ? ENTRY_UNITS : 0);

  const span = center ? 360 : FRONT_SPAN;
  const step = span / units; // degrees per seat
  const rFirst = Math.max(floorEnd + 56, MIN_SEAT_SPACING / rad(step));
  const rLast = rFirst + Math.max(rows.length - 1, 0) * ROW_PITCH;
  const rMax = rLast + SEAT;

  // Seating arc: horseshoe centred on 90° (below the stage), or a bowl that starts and
  // ends at the entry aisle at the top (270°)
  const a0 = center ? 270 + (ENTRY_UNITS / 2) * step : 90 - FRONT_SPAN / 2;
  const a1 = center ? 270 + 360 - (ENTRY_UNITS / 2) * step : 90 + FRONT_SPAN / 2;

  // Canvas
  const above = center ? rMax : Math.max(rMax * Math.sin(rad(FRONT_SPAN / 2 - 90)) + SEAT, 110);
  const sideRoom = center ? 0 : SIDE_LABEL_ROOM;
  const cx = PAD + sideRoom + rMax + 30;
  const cy = PAD + above + 30;
  const width = cx * 2;
  const height = cy + rMax + PAD + 30;

  // Seat angle: seat 1 on the left as seen from the seats, columns shared by every row
  const angleOf = (seatNumber: number) => {
    const i = seatNumber - 1;
    const block = Math.floor(i / perBlock);
    const u = i + block * AISLE_UNITS + 0.5;
    // Front: left of the audience is the far end of the arc (towards 180°+)
    return center ? a0 + u * step : a1 - u * step;
  };

  const seatPos = new Map<string, { x: number; y: number; rotate: number }>();
  for (const s of seats) {
    const r = rFirst + (rowIdx.get(s.row_label) ?? 0) * ROW_PITCH + SEAT / 2;
    const a = angleOf(s.seat_number);
    seatPos.set(s.show_seat_id, {
      x: cx + r * Math.cos(rad(a)) - SEAT / 2,
      y: cy + r * Math.sin(rad(a)) - SEAT / 2,
      rotate: a - 90, // the seat's front faces the stage
    });
  }

  // Sections become coloured tiers; a section is premium if most of its seats are
  const sectionRows = new Map<string, number[]>();
  const premiumCount = new Map<string, number>();
  for (const s of seats) {
    const name = s.section_name || "Stands";
    const list = sectionRows.get(name) ?? [];
    list.push(rowIdx.get(s.row_label) ?? 0);
    sectionRows.set(name, list);
    if (s.seat_type === "premium") premiumCount.set(name, (premiumCount.get(name) ?? 0) + 1);
  }
  let colorIdx = 0;
  const bands: ArenaBand[] = Array.from(sectionRows.entries())
    .map(([name, idxs]) => ({ name, first: Math.min(...idxs), last: Math.max(...idxs), count: idxs.length }))
    .sort((a, b) => a.first - b.first)
    .map((b) => ({
      name: b.name,
      color:
        (premiumCount.get(b.name) ?? 0) * 2 > b.count
          ? PREMIUM_COLOR
          : BAND_COLORS[colorIdx++ % BAND_COLORS.length],
      rIn: rFirst + b.first * ROW_PITCH - 6,
      rOut: rFirst + b.last * ROW_PITCH + SEAT + 6,
    }));

  // Standing rings, labelled where the floor is widest (straight below the stage)
  const rings: ArenaRing[] = orderedZones.map((z, i) => {
    const rIn = floorStart + i * ringWidth;
    const rOut = rIn + ringWidth - 8;
    return {
      id: z.id,
      isFanPit: isFanPitZone(z),
      rIn,
      rOut,
      labelX: cx,
      labelY: cy + (rIn + rOut) / 2,
    };
  });

  // Row letters next to the end seats of each tier: both sides of a bowl's entry aisle,
  // the right end of a horseshoe (its left end carries the section names)
  const pad = 0.9 * step;
  const rowLabels = rows.flatMap((label, i) => {
    const r = rFirst + i * ROW_PITCH + SEAT / 2;
    return (center ? [a0 - pad, a1 + pad] : [a0 - pad]).map((a) => ({
      label,
      x: cx + r * Math.cos(rad(a)),
      y: cy + r * Math.sin(rad(a)) + 4,
    }));
  });

  // Section names: left of the horseshoe, or in the entry aisle of a bowl
  const sectionLabels = bands.map((b) => {
    const r = (b.rIn + b.rOut) / 2;
    if (center) {
      return { text: b.name, x: cx, y: cy - r + 4, anchor: "middle" as const, color: b.color };
    }
    const a = a1 + pad;
    return {
      text: b.name,
      x: cx + r * Math.cos(rad(a)),
      y: cy + r * Math.sin(rad(a)) + 4,
      anchor: "end" as const,
      color: b.color,
    };
  });

  return {
    center,
    cx,
    cy,
    a0,
    a1,
    stageW: Math.min(2 * floorEnd, 420),
    stageR,
    width,
    height,
    seats: seatPos,
    bands,
    rings,
    rowLabels,
    sectionLabels,
  };
}

// SVG path of a ring sector between two radii and two angles (degrees)
export function ringPath(cx: number, cy: number, rIn: number, rOut: number, a0: number, a1: number): string {
  if (a1 - a0 >= 359.9) {
    // Full ring: two half circles each way, filled with the even-odd rule
    const circle = (r: number) =>
      `M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy} Z`;
    return `${circle(rOut)} ${rIn > 0 ? circle(rIn) : ""}`;
  }
  const pt = (r: number, a: number) => `${cx + r * Math.cos(rad(a))} ${cy + r * Math.sin(rad(a))}`;
  const large = a1 - a0 > 180 ? 1 : 0;
  return [
    `M ${pt(rOut, a0)}`,
    `A ${rOut} ${rOut} 0 ${large} 1 ${pt(rOut, a1)}`,
    `L ${pt(rIn, a1)}`,
    `A ${rIn} ${rIn} 0 ${large} 0 ${pt(rIn, a0)}`,
    "Z",
  ].join(" ");
}
