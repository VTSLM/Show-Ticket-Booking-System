"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { useAuth } from "@/contexts/AuthContext";
import { wishlistApi } from "@/lib/api";

/**
 * Wishlist state for the current user.
 *   has(eventId)     -> is this event saved?
 *   toggle(eventId)  -> save / remove it (sends logged-out users to the login page)
 */
export function useWishlist() {
  const { profile, loading } = useAuth();
  const router = useRouter();
  const [ids, setIds] = useState<Set<string>>(new Set());
  const userId = profile?.id;

  useEffect(() => {
    if (loading) return;
    if (!userId) {
      setIds(new Set());
      return;
    }
    wishlistApi
      .ids()
      .then((r) => setIds(new Set(r.event_ids)))
      .catch(() => {});
  }, [userId, loading]);

  const toggle = useCallback(
    async (eventId: string) => {
      if (!userId) {
        toast.error("Log in to save shows to your wishlist");
        router.push("/auth/login");
        return;
      }
      const wasSaved = ids.has(eventId);
      const apply = (saved: boolean) =>
        setIds((prev) => {
          const next = new Set(prev);
          if (saved) next.add(eventId);
          else next.delete(eventId);
          return next;
        });

      apply(!wasSaved); // update the heart immediately
      try {
        if (wasSaved) await wishlistApi.remove(eventId);
        else await wishlistApi.add(eventId);
        toast.success(wasSaved ? "Removed from wishlist" : "Added to wishlist");
      } catch (e: any) {
        apply(wasSaved); // put it back
        toast.error(e.message || "Could not update wishlist");
      }
    },
    [ids, userId, router]
  );

  return { ids, has: (eventId: string) => ids.has(eventId), toggle };
}
