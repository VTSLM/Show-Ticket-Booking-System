const STORAGE_PREFIX = 'show_seats_selection_';

export function saveSeatSelection(showId: string, seatIds: string[]): void {
  if (typeof window === 'undefined') return;
  try {
    const key = `${STORAGE_PREFIX}${showId}`;
    if (seatIds.length === 0) {
      sessionStorage.removeItem(key);
    } else {
      sessionStorage.setItem(key, JSON.stringify(seatIds));
    }
  } catch (e) {
    console.warn('Failed to save seat selection to sessionStorage:', e);
  }
}

export function getSavedSeatSelection(showId: string): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const key = `${STORAGE_PREFIX}${showId}`;
    const data = sessionStorage.getItem(key);
    if (!data) return [];
    const parsed = JSON.parse(data);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.warn('Failed to parse seat selection from sessionStorage:', e);
    return [];
  }
}

export function clearSavedSeatSelection(showId: string): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.removeItem(`${STORAGE_PREFIX}${showId}`);
  } catch (e) {
    // Ignore storage removal errors
  }
}
