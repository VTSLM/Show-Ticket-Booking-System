// Which venue layouts suit which event types (#168). Used when a manager schedules a show.
export type LayoutType = "cinema" | "concert" | "theatre" | "other";

export const LAYOUT_LABELS: Record<string, string> = {
  cinema: "Cinema (screen + rows)",
  concert: "Concert arena (stage + zones)",
  theatre: "Theatre (stage + stalls)",
  other: "General admission",
};

/** True when the screen's layout is a natural fit for the event type. */
export function layoutFits(eventType?: string | null, layoutType?: string | null): boolean {
  const event = (eventType || "movie").toLowerCase();
  const layout = (layoutType || "cinema").toLowerCase();
  if (event === "movie") return layout === "cinema";
  if (event === "concert") return layout === "concert" || layout === "other";
  if (event === "theatre") return layout === "theatre";
  return layout !== "cinema"; // comedy and other live events: any stage layout
}

/** A short warning for a mismatched choice, or null when it fits. */
export function layoutWarning(eventType?: string | null, layoutType?: string | null): string | null {
  if (layoutFits(eventType, layoutType)) return null;
  const event = (eventType || "movie").toLowerCase();
  const layout = (layoutType || "cinema").toLowerCase();
  if (event === "movie") {
    return `Movies are shown on a cinema screen, but this is a ${LAYOUT_LABELS[layout] ?? layout} layout.`;
  }
  if (layout === "cinema") {
    return "This is a cinema screen. Customers will see a stage instead of the screen; check that the seating suits a live event.";
  }
  if (event === "concert") return "Concerts usually use a concert arena layout (stage, fan pits, standing zones).";
  if (event === "theatre") return "Theatre usually uses a theatre layout (stage, stalls, balcony).";
  return null;
}
