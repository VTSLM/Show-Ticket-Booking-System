"use client";
import { useEffect, useState } from "react";

// Icon for the placeholder, by event type. Unknown types get a neutral ticket.
const TYPE_ICONS: Record<string, string> = {
  movie: "🎬",
  concert: "🎵",
  theatre: "🎭",
  comedy: "🎤",
  sports: "🏟️",
};

export function posterIcon(eventType?: string | null): string {
  return TYPE_ICONS[(eventType || "").toLowerCase()] ?? "🎟️";
}

/**
 * An event poster that shows a neutral placeholder when the event has no poster
 * or the image fails to load. Never substitutes another event's poster.
 */
export default function EventPoster({
  src,
  alt,
  eventType,
  className,
  placeholderClassName,
  iconClassName = "text-6xl",
}: {
  src?: string | null;
  alt: string;
  eventType?: string | null;
  className: string;
  placeholderClassName: string;
  iconClassName?: string;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);

  if (!src || failed) {
    return (
      <div className={placeholderClassName} role="img" aria-label={`${alt} (no poster available)`}>
        <span className={iconClassName} aria-hidden="true">
          {posterIcon(eventType)}
        </span>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      className={className}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}
