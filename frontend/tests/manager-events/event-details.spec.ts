import { test, expect, Page } from "@playwright/test";

// Manager event details form (#169). Firebase sign-in and the API are faked, so no backend
// or real account is needed: a manager session is planted where the Firebase SDK keeps it.

const API_KEY = process.env.NEXT_PUBLIC_FIREBASE_API_KEY || "";
// The fake session is stored under the app's Firebase key, so run with the same
// NEXT_PUBLIC_FIREBASE_API_KEY the frontend was built with.
test.skip(!API_KEY, "Set NEXT_PUBLIC_FIREBASE_API_KEY to the value the frontend was built with");
const ORG = { id: "11111111-1111-1111-1111-111111111111", legal_name: "Demo Live", business_type: "company", verification_status: "APPROVED" };
const MOVIE = {
  id: "22222222-2222-2222-2222-222222222222", title: "Dune: Part Two", event_type: "movie", status: "draft",
  language: "English", duration_minutes: 166, genre: "Sci-Fi", description: "Paul joins the Fremen.",
  poster_url: null, backdrop_url: null, release_date: "2024-03-01", certificate: "UA", formats: ["2D", "IMAX"],
  cast_crew: JSON.stringify([{ name: "Timothée Chalamet", role: "Paul Atreides" }]), artists: "[]",
  terms_and_conditions: "No outside food.", organization_name: "Demo Live",
};

async function signInAsManager(page: Page) {
  const fakeJwt = ["e30", btoa(JSON.stringify({ exp: 4102444800, iat: 1700000000, sub: "mgr", user_id: "mgr" })), "sig"].join(".");
  await page.addInitScript(({ apiKey, token }) => {
    const user = {
      uid: "mgr", email: "manager@example.com", emailVerified: true, isAnonymous: false, providerData: [],
      stsTokenManager: { refreshToken: "r", accessToken: token, expirationTime: 4102444800000 },
      createdAt: "1700000000000", lastLoginAt: "1700000000000", apiKey, appName: "[DEFAULT]",
    };
    const open = indexedDB.open("firebaseLocalStorageDb", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("firebaseLocalStorage", { keyPath: "fbase_key" });
    open.onsuccess = () => {
      const tx = open.result.transaction("firebaseLocalStorage", "readwrite");
      tx.objectStore("firebaseLocalStorage").put({ fbase_key: `firebase:authUser:${apiKey}:[DEFAULT]`, value: user });
    };
  }, { apiKey: API_KEY, token: fakeJwt });
  // Firebase checks the stored account once on start-up
  await page.route("**/identitytoolkit.googleapis.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ users: [{ localId: "mgr", email: "manager@example.com", emailVerified: true }] }) }));
}

type Calls = { created: any[]; updated: any[]; uploads: number };

async function mockApi(page: Page): Promise<Calls> {
  const calls: Calls = { created: [], updated: [], uploads: 0 };
  let events = [MOVIE];
  await page.route(/127\.0\.0\.1:3100\/(api|auth)\//, async (route) => {
    const req = route.request();
    const url = req.url();
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (url.includes("/auth/verify-token")) {
      return json({ user: { id: "mgr", name: "Manager", email: "manager@example.com", roles: ["manager"], status: "active" }, session: null });
    }
    if (url.includes("/api/verification/organizer/applications/me")) return json([ORG]);
    if (url.endsWith("/api/manager/event-images")) {
      calls.uploads += 1;
      return json({ url: "https://example.supabase.co/storage/v1/object/public/event-images/mgr/poster-1.jpg" });
    }
    if (url.endsWith("/api/manager/events") && req.method() === "POST") {
      const body = req.postDataJSON();
      calls.created.push(body);
      events = [{ ...MOVIE, ...body, id: "33333333-3333-3333-3333-333333333333" }, ...events];
      return json(events[0]);
    }
    if (url.endsWith("/api/manager/events")) return json(events);
    const patch = url.match(/\/api\/manager\/events\/([^/?]+)$/);
    if (patch && req.method() === "PATCH") {
      const body = req.postDataJSON();
      calls.updated.push(body);
      return json({ ...MOVIE, ...body });
    }
    return json([]);
  });
  return calls;
}

async function openEventsTab(page: Page) {
  await page.goto("/manager");
  await page.getByRole("button", { name: /^Events/ }).first().click();
  await expect(page.getByText("Create Event", { exact: true })).toBeVisible();
}

const createForm = (page: Page) => page.getByTestId("event-details-form").first();

test("the form shows movie fields for movies and artists for live events", async ({ page }) => {
  await signInAsManager(page);
  await mockApi(page);
  await openEventsTab(page);
  const form = createForm(page);
  await expect(form.getByTestId("formats")).toBeVisible();
  await expect(form.getByTestId("cast-crew")).toBeVisible();
  await expect(form.getByText("Release date")).toBeVisible();

  await form.locator("select").nth(1).selectOption("concert");
  await expect(form.getByTestId("formats")).toHaveCount(0);
  await expect(form.getByTestId("cast-crew")).toHaveCount(0);
  await expect(form.getByText("Release date")).toHaveCount(0);
  await expect(form.getByTestId("artists")).toBeVisible();
});

test("a manager creates a concert with poster, description and artists", async ({ page }) => {
  await signInAsManager(page);
  const calls = await mockApi(page);
  await openEventsTab(page);
  const form = createForm(page);

  await form.getByLabel("Title").fill("Neon Skyline Tour");
  await form.locator("select").nth(1).selectOption("concert");
  await form.getByLabel("Language").fill("English");
  await form.getByLabel("About the event").fill("A night of synth-pop.");
  await form.getByTestId("poster-picker").locator('input[type="file"]').setInputFiles({
    name: "poster.png", mimeType: "image/png",
    buffer: Buffer.from("89504e470d0a1a0a0000000d4948445200000001000000010806000000", "hex"),
  });
  await expect(form.getByRole("img", { name: "Poster preview" })).toHaveAttribute("src", /poster-1\.jpg/);
  await form.getByRole("button", { name: "+ Add artist" }).click();
  await form.getByPlaceholder("Name").fill("The Neon Lights");
  await form.getByPlaceholder(/Role/).fill("Headliner");
  await form.getByRole("button", { name: "Create Event (Draft)" }).click();

  await expect.poll(() => calls.created.length).toBe(1);
  const body = calls.created[0];
  expect(calls.uploads).toBe(1);
  expect(body).toMatchObject({
    title: "Neon Skyline Tour", event_type: "concert", description: "A night of synth-pop.",
    poster_url: expect.stringContaining("poster-1.jpg"), status: "draft", organizer_id: ORG.id,
    artists: [{ name: "The Neon Lights", role: "Headliner" }], cast_crew: [], formats: [], certificate: null,
  });
});

test("a manager edits an existing movie and its saved details are prefilled", async ({ page }) => {
  await signInAsManager(page);
  const calls = await mockApi(page);
  await openEventsTab(page);
  await page.getByRole("button", { name: "Edit details" }).click();
  const form = page.getByTestId("event-details-form").nth(1);

  await expect(form.getByLabel("Title")).toHaveValue("Dune: Part Two");
  await expect(form.getByLabel("About the event")).toHaveValue("Paul joins the Fremen.");
  await expect(form.getByPlaceholder("Name")).toHaveValue("Timothée Chalamet");
  await expect(form.getByLabel("Release date")).toHaveValue("2024-03-01");

  await form.getByLabel("About the event").fill("Paul unites the Fremen.");
  await form.getByRole("button", { name: "Save changes" }).click();
  await expect.poll(() => calls.updated.length).toBe(1);
  expect(calls.updated[0]).toMatchObject({
    description: "Paul unites the Fremen.", release_date: "2024-03-01", certificate: "UA",
    formats: ["2D", "IMAX"], cast_crew: [{ name: "Timothée Chalamet", role: "Paul Atreides" }], artists: [],
  });
  await expect(page.getByTestId("event-details-form")).toHaveCount(1); // edit form closed
});
