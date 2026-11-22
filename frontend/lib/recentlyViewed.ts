// "Recently viewed" shows, kept in this browser's localStorage (nothing is sent to the server).

export const RECENTLY_VIEWED_KEY = "ticketflow_recently_viewed";
export const RECENTLY_VIEWED_MAX = 10;

export interface RecentlyViewedItem {
  event_id?: string | null;
  show_id?: string | null;
  title: string;
  poster_url?: string | null;
  event_type?: string | null;
  language?: string | null;
  genre?: string | null;
  viewed_at: number;
}

const keyOf = (item: Pick<RecentlyViewedItem, "event_id" | "show_id" | "title">): string =>
  String(item.event_id || item.show_id || item.title).toLowerCase();

function read(): RecentlyViewedItem[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENTLY_VIEWED_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((i) => i && typeof i.title === "string" && (i.event_id || i.show_id))
      .slice(0, RECENTLY_VIEWED_MAX);
  } catch {
    return [];
  }
}

function write(items: RecentlyViewedItem[]): void {
  try {
    window.localStorage.setItem(RECENTLY_VIEWED_KEY, JSON.stringify(items));
  } catch {
    // storage full or blocked: the row simply stays empty
  }
}

/** Newest first. */
export function getRecentlyViewed(): RecentlyViewedItem[] {
  return read();
}

/** Remember a show; viewing it again moves it to the front. */
export function addRecentlyViewed(item: Omit<RecentlyViewedItem, "viewed_at">): void {
  if (typeof window === "undefined") return;
  if (!item.title || !(item.event_id || item.show_id)) return;
  const entry: RecentlyViewedItem = { ...item, viewed_at: Date.now() };
  const rest = read().filter((i) => keyOf(i) !== keyOf(entry));
  write([entry, ...rest].slice(0, RECENTLY_VIEWED_MAX));
}

export function clearRecentlyViewed(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(RECENTLY_VIEWED_KEY);
  } catch {
    // ignore
  }
}
