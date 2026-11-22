"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  useCallback,
  ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { auth, onAuthStateChanged, signOut } from "@/lib/firebase";
import { needsEmailVerification } from "@/lib/emailVerification";
import {
  authApi,
  getActiveSessionId,
  setActiveSessionId,
  onSessionExpired,
} from "@/lib/api";
import { SessionTimeoutModal } from "@/components/SessionTimeoutModal";

interface UserProfile {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  roles: string[];
  status: string;
}

interface UserSession {
  id: string;
  user_id: string;
  role: string;
  timeout_seconds: number;
  warning_lead_seconds: number;
}

interface AuthCtx {
  user: any | null; // Firebase user
  profile: UserProfile | null;
  session: UserSession | null;
  loading: boolean;
  isAdmin: boolean;
  isManager: boolean;
  isCustomer: boolean;
  isCritic: boolean;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  extendSession: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>({} as AuthCtx);

const LAST_ACTIVITY_KEY = "ticketflow_last_activity";
const BROADCAST_CHANNEL_NAME = "ticketflow_session_sync";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<any | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [session, setSession] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);

  // Inactivity warning modal states
  const [showWarning, setShowWarning] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(120);
  const [isExtending, setIsExtending] = useState(false);

  const lastActivityRef = useRef<number>(Date.now());
  const channelRef = useRef<BroadcastChannel | null>(null);
  const isLoggingOutRef = useRef<boolean>(false);
  const router = useRouter();

  const refreshProfile = async () => {
    if (!auth.currentUser) return;
    try {
      const p = (await authApi.me()) as UserProfile;
      setProfile(p);
    } catch {
      setProfile(null);
    }
  };

  // Perform clean inactivity logout
  const handleInactivityLogout = useCallback(
    async (isCrossTab = false) => {
      if (isLoggingOutRef.current) return;
      isLoggingOutRef.current = true;

      const currentSessionId = getActiveSessionId();
      setShowWarning(false);

      if (currentSessionId && !isCrossTab) {
        try {
          await authApi.logoutSession(currentSessionId);
        } catch {
          // Best-effort server notification
        }
      }

      setActiveSessionId(null);
      if (typeof window !== "undefined") {
        localStorage.removeItem(LAST_ACTIVITY_KEY);
      }

      try {
        await signOut(auth);
      } catch {
        // Ignored
      }

      setUser(null);
      setProfile(null);
      setSession(null);

      if (!isCrossTab && channelRef.current) {
        try {
          channelRef.current.postMessage({ type: "LOGOUT", reason: "inactivity" });
        } catch {
          // Channel error fallback
        }
      }

      router.push("/auth/login?reason=inactivity");
      toast.error("Your session expired due to inactivity. Please log in again.");

      setTimeout(() => {
        isLoggingOutRef.current = false;
      }, 1000);
    },
    [router]
  );

  // Manual explicit logout
  const logout = useCallback(async () => {
    if (isLoggingOutRef.current) return;
    isLoggingOutRef.current = true;

    const currentSessionId = getActiveSessionId();
    setShowWarning(false);

    if (currentSessionId) {
      try {
        await authApi.logoutSession(currentSessionId);
      } catch {
        // Best-effort
      }
    }

    setActiveSessionId(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem(LAST_ACTIVITY_KEY);
    }

    try {
      await signOut(auth);
    } catch {
      // Ignored
    }

    setUser(null);
    setProfile(null);
    setSession(null);

    if (channelRef.current) {
      try {
        channelRef.current.postMessage({ type: "LOGOUT", reason: "manual" });
      } catch {
        // Ignored
      }
    }

    setTimeout(() => {
      isLoggingOutRef.current = false;
    }, 1000);
  }, []);

  // "Stay Logged In" action
  const extendSession = useCallback(async () => {
    const currentSessionId = session?.id || getActiveSessionId();
    if (!currentSessionId) return;

    setIsExtending(true);
    try {
      const res = (await authApi.heartbeat(currentSessionId)) as any;
      if (res?.status === "active") {
        const now = Date.now();
        lastActivityRef.current = now;
        if (typeof window !== "undefined") {
          localStorage.setItem(LAST_ACTIVITY_KEY, now.toString());
        }
        setShowWarning(false);

        if (channelRef.current) {
          channelRef.current.postMessage({ type: "ACTIVITY", timestamp: now });
        }
        toast.success("Session extended");
      }
    } catch (err: any) {
      // If server rejected heartbeat because session expired
      if (
        err?.message?.toLowerCase().includes("inactivity") ||
        err?.message?.toLowerCase().includes("expired")
      ) {
        await handleInactivityLogout();
      } else {
        toast.error("Could not extend session. Please check your connection.");
      }
    } finally {
      setIsExtending(false);
    }
  }, [session, handleInactivityLogout]);

  // Hook into 401 session-expired responses across all API calls
  useEffect(() => {
    onSessionExpired(() => {
      handleInactivityLogout();
    });
  }, [handleInactivityLogout]);

  // Initialize and verify authentication + session
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (firebaseUser) => {
      // An account whose email isn't verified yet counts as logged out everywhere;
      // the verify-email page works with auth.currentUser directly (#208)
      if (firebaseUser && needsEmailVerification(firebaseUser)) {
        setUser(null);
        setProfile(null);
        setSession(null);
        setActiveSessionId(null);
        setLoading(false);
        return;
      }
      setUser(firebaseUser);
      if (firebaseUser) {
        try {
          const idToken = await firebaseUser.getIdToken();
          const existingSessionId = getActiveSessionId();
          const res = (await authApi.verifyToken(idToken, existingSessionId)) as any;
          setProfile(res.user);
          if (res.session) {
            setSession(res.session);
            setActiveSessionId(res.session.id);
            const now = Date.now();
            lastActivityRef.current = now;
            if (typeof window !== "undefined") {
              localStorage.setItem(LAST_ACTIVITY_KEY, now.toString());
            }
          }
        } catch {
          setProfile(null);
          setSession(null);
          setActiveSessionId(null);
        }
      } else {
        setProfile(null);
        setSession(null);
        setActiveSessionId(null);
      }
      setLoading(false);
    });
    return unsub;
  }, []);

  // Multi-tab synchronization via BroadcastChannel & storage event fallback
  useEffect(() => {
    if (typeof window === "undefined") return;

    try {
      if ("BroadcastChannel" in window) {
        channelRef.current = new BroadcastChannel(BROADCAST_CHANNEL_NAME);
        channelRef.current.onmessage = (event) => {
          const data = event.data;
          if (!data) return;

          if (data.type === "ACTIVITY" && data.timestamp) {
            lastActivityRef.current = Math.max(lastActivityRef.current, data.timestamp);
            setShowWarning(false);
          } else if (data.type === "LOGOUT") {
            handleInactivityLogout(true);
          }
        };
      }
    } catch {
      // BroadcastChannel unavailable
    }

    const handleStorageEvent = (e: StorageEvent) => {
      if (e.key === LAST_ACTIVITY_KEY && e.newValue) {
        const ts = parseInt(e.newValue, 10);
        if (!isNaN(ts)) {
          lastActivityRef.current = Math.max(lastActivityRef.current, ts);
          setShowWarning(false);
        }
      }
    };

    window.addEventListener("storage", handleStorageEvent);

    return () => {
      window.removeEventListener("storage", handleStorageEvent);
      if (channelRef.current) {
        try {
          channelRef.current.close();
        } catch {
          // Ignore close error
        }
      }
    };
  }, [handleInactivityLogout]);

  // Meaningful user activity tracking (keyboard, clicks, touch, scroll)
  // Excludes background polling, automated requests, or window focus
  useEffect(() => {
    if (!profile || !session) return;

    const recordUserActivity = () => {
      const now = Date.now();
      // Throttle activity updates to at most once every 10 seconds
      if (now - lastActivityRef.current < 10000) return;

      lastActivityRef.current = now;
      if (typeof window !== "undefined") {
        localStorage.setItem(LAST_ACTIVITY_KEY, now.toString());
      }

      if (channelRef.current) {
        try {
          channelRef.current.postMessage({ type: "ACTIVITY", timestamp: now });
        } catch {
          // Channel error fallback
        }
      }

      if (showWarning) {
        setShowWarning(false);
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        // Check sync on tab refocus without marking artificial activity
        if (typeof window !== "undefined") {
          const stored = localStorage.getItem(LAST_ACTIVITY_KEY);
          if (stored) {
            const ts = parseInt(stored, 10);
            if (!isNaN(ts)) {
              lastActivityRef.current = Math.max(lastActivityRef.current, ts);
            }
          }
        }
      }
    };

    window.addEventListener("keydown", recordUserActivity, { passive: true });
    window.addEventListener("mousedown", recordUserActivity, { passive: true });
    window.addEventListener("touchstart", recordUserActivity, { passive: true });
    window.addEventListener("scroll", recordUserActivity, { passive: true });
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("keydown", recordUserActivity);
      window.removeEventListener("mousedown", recordUserActivity);
      window.removeEventListener("touchstart", recordUserActivity);
      window.removeEventListener("scroll", recordUserActivity);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [profile, session, showWarning]);

  // Inactivity timer evaluation loop (runs once per second)
  useEffect(() => {
    if (!profile || !session) {
      setShowWarning(false);
      return;
    }

    const interval = setInterval(() => {
      // Read latest activity from cross-tab storage
      if (typeof window !== "undefined") {
        const stored = localStorage.getItem(LAST_ACTIVITY_KEY);
        if (stored) {
          const ts = parseInt(stored, 10);
          if (!isNaN(ts) && ts > lastActivityRef.current) {
            lastActivityRef.current = ts;
          }
        }
      }

      const timeoutMs = (session.timeout_seconds || 1800) * 1000;
      const warningLeadMs = (session.warning_lead_seconds || 120) * 1000;
      const elapsed = Date.now() - lastActivityRef.current;
      const remainingMs = timeoutMs - elapsed;
      const remainingSec = Math.max(0, Math.ceil(remainingMs / 1000));

      if (remainingMs <= 0) {
        clearInterval(interval);
        handleInactivityLogout();
      } else if (remainingMs <= warningLeadMs) {
        setShowWarning(true);
        setRemainingSeconds(remainingSec);
      } else {
        setShowWarning(false);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [profile, session, handleInactivityLogout]);

  const roles = profile?.roles || [];
  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        session,
        loading,
        isAdmin: roles.includes("admin"),
        isManager: roles.includes("manager") || roles.includes("admin"),
        isCustomer: roles.includes("customer"),
        isCritic: roles.includes("critic") || roles.includes("admin"),
        logout,
        refreshProfile,
        extendSession,
      }}
    >
      {children}
      <SessionTimeoutModal
        isOpen={showWarning}
        remainingSeconds={remainingSeconds}
        onStayLoggedIn={extendSession}
        onLogoutNow={logout}
        isExtending={isExtending}
      />
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
