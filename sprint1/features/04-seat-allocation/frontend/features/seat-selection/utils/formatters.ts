/**
 * Indian Rupee currency formatter (e.g. ₹400).
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Formats ISO 8601 UTC timestamp to localized date & time in Asia/Kolkata.
 */
export function formatShowDateTime(isoString: string): {
  dateStr: string;
  timeStr: string;
  fullStr: string;
} {
  try {
    const date = new Date(isoString);

    const dateStr = new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date);

    const timeStr = new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }).format(date);

    return {
      dateStr,
      timeStr,
      fullStr: `${dateStr} • ${timeStr}`,
    };
  } catch (e) {
    return {
      dateStr: '',
      timeStr: '',
      fullStr: isoString,
    };
  }
}

/**
 * Formats duration in minutes to human readable string (e.g. 142 -> "2h 22m").
 */
export function formatDuration(minutes: number): string {
  if (!minutes || minutes <= 0) return '0m';
  const hrs = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hrs > 0 && mins > 0) return `${hrs}h ${mins}m`;
  if (hrs > 0) return `${hrs}h`;
  return `${mins}m`;
}

/**
 * Formats a list of seats into comma-separated labels (e.g. "C5, C6, D1").
 */
export function formatSeatNames(seats: { row_label: string; seat_number: number }[]): string {
  if (!seats || seats.length === 0) return '';
  return seats.map((s) => `${s.row_label}${s.seat_number}`).join(', ');
}
