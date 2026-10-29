import { initializeApp, getApps, getApp } from 'firebase/app';
import {
  getAuth,
  onAuthStateChanged,
  signInAnonymously,
  signOut,
  User,
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || 'AIzaSyFakeDevKeyForLocalExecution12345',
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || 'show-ticket-booking-dev.firebaseapp.com',
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'show-ticket-booking-dev',
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || 'show-ticket-booking-dev.appspot.com',
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || '123456789012',
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || '1:123456789012:web:abcdef1234567890abcdef',
};

// Singleton Firebase App
const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();
export const auth = getAuth(app);

// Local testing flag
const isDevAuth = process.env.NODE_ENV !== 'production' || process.env.NEXT_PUBLIC_ENABLE_DEV_PAYMENT_SIMULATOR === 'true';

let mockUser: { uid: string; email: string } | null = null;

export async function getIdToken(): Promise<string | null> {
  if (mockUser) {
    return 'dev-token';
  }
  const currentUser = auth.currentUser;
  if (!currentUser) {
    // If running locally in dev and mock session is active in localStorage
    if (typeof window !== 'undefined' && localStorage.getItem('bm_dev_user_signed_in') === 'true') {
      return 'dev-token';
    }
    return null;
  }
  try {
    return await currentUser.getIdToken();
  } catch (error) {
    console.error('Error fetching Firebase ID token:', error);
    return null;
  }
}

export function getCurrentUser(): { uid: string; email?: string } | null {
  if (mockUser) return mockUser;
  if (typeof window !== 'undefined' && localStorage.getItem('bm_dev_user_signed_in') === 'true') {
    return { uid: 'dev-customer-local-uid', email: 'dev@example.com' };
  }
  const u = auth.currentUser;
  if (!u) return null;
  return { uid: u.uid, email: u.email || undefined };
}

export function onAuthChange(callback: (user: { uid: string; email?: string } | null) => void): () => void {
  // Check local mock user first
  if (typeof window !== 'undefined' && localStorage.getItem('bm_dev_user_signed_in') === 'true') {
    callback({ uid: 'dev-customer-local-uid', email: 'dev@example.com' });
  }

  const unsubscribe = onAuthStateChanged(auth, (user: User | null) => {
    if (user) {
      callback({ uid: user.uid, email: user.email || undefined });
    } else if (typeof window !== 'undefined' && localStorage.getItem('bm_dev_user_signed_in') === 'true') {
      callback({ uid: 'dev-customer-local-uid', email: 'dev@example.com' });
    } else {
      callback(null);
    }
  });

  return unsubscribe;
}

export async function signInDevUser(): Promise<void> {
  if (typeof window !== 'undefined') {
    localStorage.setItem('bm_dev_user_signed_in', 'true');
  }
  mockUser = { uid: 'dev-customer-local-uid', email: 'dev@example.com' };
}

export async function signOutUser(): Promise<void> {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('bm_dev_user_signed_in');
  }
  mockUser = null;
  try {
    await signOut(auth);
  } catch (e) {
    // Ignore sign out errors if already unauthenticated
  }
}
