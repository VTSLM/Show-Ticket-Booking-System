"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { notificationsApi, NotificationItem } from "@/lib/notificationsApi";

export default function NotificationBell() {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchNotifications = async () => {
    try {
      const res = await notificationsApi.list(15);
      setNotifications(res.notifications || []);
      setUnreadCount(res.unread_count || 0);
    } catch {
      // Graceful fallback
    }
  };

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 25000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleMarkAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await notificationsApi.markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {}
  };

  const handleMarkAllRead = async () => {
    try {
      setLoading(true);
      await notificationsApi.markAllAsRead();
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, read_at: new Date().toISOString() }))
      );
      setUnreadCount(0);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative rounded-full p-1.5 text-gray-300 hover:text-white hover:bg-white/5 transition-colors focus:outline-none"
        title="Notifications"
        aria-label="Notifications"
      >
        <span className="text-lg">🔔</span>
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white shadow-md">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 overflow-hidden rounded-2xl border border-[#2a2f45] bg-[#121524] text-white shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-150">
          <div className="border-b border-[#2a2f45] bg-[#181c30] px-4 py-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              Notifications
              {unreadCount > 0 && (
                <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[11px] font-semibold text-blue-400">
                  {unreadCount} new
                </span>
              )}
            </h3>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                disabled={loading}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors disabled:opacity-50"
              >
                Mark all as read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto divide-y divide-[#1e2338]">
            {notifications.length === 0 ? (
              <div className="p-6 text-center text-xs text-gray-400">
                No notifications right now.
              </div>
            ) : (
              notifications.map((notif) => {
                const p = notif.payload || {};
                const isUnread = !notif.read_at;
                const linkHref = p.booking_id ? `/bookings/${p.booking_id}` : "#";

                return (
                  <Link
                    key={notif.id}
                    href={linkHref}
                    onClick={() => setIsOpen(false)}
                    className={`block p-3.5 transition-colors text-xs hover:bg-[#1a1f36] ${
                      isUnread ? "bg-blue-500/[0.04]" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <div className="font-semibold text-gray-200 flex items-center gap-1.5">
                          {notif.event_name === "booking.cancelled" && "🎟️ Booking Cancelled"}
                          {notif.event_name === "refund.successful" && "✅ Refund Processed"}
                          {notif.event_name === "refund.initiated" && "⏳ Refund Initiated"}
                          {notif.event_name === "refund.failed" && "⚠️ Refund Action Required"}
                          {!notif.event_name.startsWith("refund") && !notif.event_name.startsWith("booking") && notif.event_name}
                          {isUnread && (
                            <span className="h-1.5 w-1.5 rounded-full bg-blue-400 inline-block" />
                          )}
                        </div>
                        <p className="text-gray-400 text-[11px] leading-relaxed">
                          {p.event_title && `${p.event_title} • `}
                          {p.refund_amount !== undefined && `Refund: ₹${Number(p.refund_amount).toFixed(2)}`}
                          {p.reason && ` • ${p.reason}`}
                        </p>
                        <span className="text-[10px] text-gray-500">
                          {new Date(notif.created_at).toLocaleTimeString("en-IN", {
                            hour: "2-digit",
                            minute: "2-digit",
                            day: "numeric",
                            month: "short",
                          })}
                        </span>
                      </div>
                      {isUnread && (
                        <button
                          onClick={(e) => handleMarkAsRead(notif.id, e)}
                          title="Mark read"
                          className="text-gray-400 hover:text-white p-1 text-xs"
                        >
                          ✓
                        </button>
                      )}
                    </div>
                  </Link>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
