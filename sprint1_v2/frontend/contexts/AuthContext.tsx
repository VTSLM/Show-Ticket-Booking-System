"use client";
import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { auth, onAuthStateChanged, signOut } from "@/lib/firebase";
import { authApi } from "@/lib/api";

interface UserProfile {
  id: string;
  name: string;
  email: string;
  roles: string[];
  status: string;
}

interface AuthCtx {
  user: any | null;          // Firebase user
  profile: UserProfile | null;
  loading: boolean;
  isAdmin: boolean;
  isManager: boolean;
  isCustomer: boolean;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthCtx>({} as AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<any | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshProfile = async () => {
    if (!auth.currentUser) return;
    try {
      const p = await authApi.me() as UserProfile;
      setProfile(p);
    } catch {
      setProfile(null);
    }
  };

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        try {
          const idToken = await firebaseUser.getIdToken();
          const res = await authApi.verifyToken(idToken) as any;
          setProfile(res.user);
        } catch {
          setProfile(null);
        }
      } else {
        setProfile(null);
      }
      setLoading(false);
    });
    return unsub;
  }, []);

  const logout = async () => {
    await signOut(auth);
    setUser(null);
    setProfile(null);
  };

  const roles = profile?.roles || [];
  return (
    <AuthContext.Provider value={{
      user, profile, loading,
      isAdmin: roles.includes("admin"),
      isManager: roles.includes("manager") || roles.includes("admin"),
      isCustomer: roles.includes("customer"),
      logout,
      refreshProfile,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
