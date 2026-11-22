import { Page, expect } from "@playwright/test";

// Signs a test browser in without a real Firebase account: plants a session where the
// Firebase SDK keeps it (IndexedDB) and answers the backend's login check. Use it only
// with mocked API routes. Run the tests with the NEXT_PUBLIC_FIREBASE_API_KEY the
// frontend was built with, since the session is stored under that key.

export const FIREBASE_API_KEY = process.env.NEXT_PUBLIC_FIREBASE_API_KEY || "";

export async function fakeLogin(page: Page, roles: string[] = ["customer"], name = "Test User") {
  const uid = `test-${roles.join("-")}`;
  const fakeJwt = ["e30", Buffer.from(JSON.stringify({ exp: 4102444800, iat: 1700000000, sub: uid, user_id: uid })).toString("base64"), "sig"].join(".");
  await page.addInitScript(({ apiKey, token, uid }) => {
    const user = {
      uid, email: `${uid}@example.com`, emailVerified: true, isAnonymous: false, providerData: [],
      stsTokenManager: { refreshToken: "r", accessToken: token, expirationTime: 4102444800000 },
      createdAt: "1700000000000", lastLoginAt: "1700000000000", apiKey, appName: "[DEFAULT]",
    };
    const open = indexedDB.open("firebaseLocalStorageDb", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("firebaseLocalStorage", { keyPath: "fbase_key" });
    open.onsuccess = () => {
      const tx = open.result.transaction("firebaseLocalStorage", "readwrite");
      tx.objectStore("firebaseLocalStorage").put({ fbase_key: `firebase:authUser:${apiKey}:[DEFAULT]`, value: user });
    };
  }, { apiKey: FIREBASE_API_KEY, token: fakeJwt, uid });

  // Firebase checks the stored account once on start-up
  await page.route("**/identitytoolkit.googleapis.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ users: [{ localId: uid, email: `${uid}@example.com`, emailVerified: true }] }) }));
  // The backend's login check returns the profile and roles
  await page.route("**/auth/verify-token", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { id: uid, name, email: `${uid}@example.com`, roles, status: "active" }, session: null }) }));
}

// Waits until the app shows the signed-in user (the navbar shows their name)
export async function waitForLogin(page: Page, name = "Test User") {
  await expect(page.getByText(name).first()).toBeVisible();
}
