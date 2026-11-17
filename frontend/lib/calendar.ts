// "Add to Calendar" helpers: a Google Calendar link and a downloadable .ics file
// (the .ics opens in Apple Calendar, Outlook and most other calendar apps).

export interface CalendarEvent {
  title: string;
  start: Date;
  end: Date;
  location?: string;
  description?: string;
  uid: string;
}

const DEFAULT_DURATION_MIN = 180; // used only when the show has no end time or duration

/** Build the calendar event for a booking returned by GET /api/bookings/{id}. */
export function bookingToCalendarEvent(booking: any, bookingId: string): CalendarEvent | null {
  if (!booking?.start_time) return null;
  const start = new Date(booking.start_time);
  if (Number.isNaN(start.getTime())) return null;

  let end = booking.end_time ? new Date(booking.end_time) : null;
  if (!end || Number.isNaN(end.getTime()) || end <= start) {
    const minutes = Number(booking.duration_minutes) > 0 ? Number(booking.duration_minutes) : DEFAULT_DURATION_MIN;
    end = new Date(start.getTime() + minutes * 60_000);
  }

  const seats = Array.isArray(booking.seats_info)
    ? booking.seats_info
        .map((s: any) => `${s.row_label ?? ""}${s.seat_number ?? ""}`.trim())
        .filter(Boolean)
        .join(", ")
    : "";

  const place = [booking.venue_name, booking.screen_name].filter(Boolean).join(" - ");
  const location = [place, booking.address, booking.city].filter(Boolean).join(", ");

  const lines = [
    `Booking ID: ${String(bookingId).slice(0, 8).toUpperCase()}`,
    seats ? `Seats: ${seats}` : "",
    "Show your TicketFlow ticket (QR code) at the entrance.",
  ].filter(Boolean);

  return {
    title: booking.event_title || "TicketFlow booking",
    start,
    end,
    location,
    description: lines.join("\n"),
    uid: `${bookingId}@ticketflow`,
  };
}

// 2026-11-16T10:30:00.000Z -> 20261116T103000Z
const toIcsDate = (d: Date) => d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");

export function googleCalendarUrl(ev: CalendarEvent): string {
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: ev.title,
    dates: `${toIcsDate(ev.start)}/${toIcsDate(ev.end)}`,
    details: ev.description ?? "",
    location: ev.location ?? "",
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

const escapeIcs = (s: string) =>
  s.replace(/\\/g, "\\\\").replace(/;/g, "\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");

// iCalendar lines should be at most 75 characters; longer ones continue on the next line after a space
const foldLine = (line: string) => {
  const parts: string[] = [];
  let rest = line;
  while (rest.length > 73) {
    parts.push(rest.slice(0, 73));
    rest = " " + rest.slice(73);
  }
  parts.push(rest);
  return parts.join("\r\n");
};

export function buildIcs(ev: CalendarEvent): string {
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//TicketFlow//Booking//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "BEGIN:VEVENT",
    `UID:${ev.uid}`,
    `DTSTAMP:${toIcsDate(new Date())}`,
    `DTSTART:${toIcsDate(ev.start)}`,
    `DTEND:${toIcsDate(ev.end)}`,
    `SUMMARY:${escapeIcs(ev.title)}`,
    ev.location ? `LOCATION:${escapeIcs(ev.location)}` : "",
    ev.description ? `DESCRIPTION:${escapeIcs(ev.description)}` : "",
    // reminder 2 hours before the show
    "BEGIN:VALARM",
    "TRIGGER:-PT2H",
    "ACTION:DISPLAY",
    `DESCRIPTION:${escapeIcs(ev.title + " starts in 2 hours")}`,
    "END:VALARM",
    "END:VEVENT",
    "END:VCALENDAR",
  ].filter(Boolean);
  return lines.map(foldLine).join("\r\n") + "\r\n";
}

export function downloadIcs(ev: CalendarEvent, fileName = "ticketflow-booking.ics") {
  const blob = new Blob([buildIcs(ev)], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
