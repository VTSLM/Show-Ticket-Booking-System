import { test, expect, Page } from "@playwright/test";

// Bugs found on the deployed app (20 Nov). The API is mocked, so no backend is needed.
const SHOW = (id: string, venue: string) => ({
  show_id: id, id, start_time: "2030-01-10T14:00:00Z", screen_name: "Main Arena",
  venue_name: venue, venue_id: venue, city: "Mumbai", base_price: 2200,
});
const CONCERT = "55555555-5555-5555-5555-555555555555";
const MOVIE = "66666666-6666-6666-6666-666666666666";
const EVENTS: Record<string, any> = {
  [CONCERT]: {
    title: "Arijit Live", event_type: "concert", status: "published",
    upcoming_shows: [SHOW("c1", "Galaxy"), SHOW("c2", "Dome")],
  },
  [MOVIE]: {
    title: "Dune", event_type: "movie", status: "published",
    upcoming_shows: [SHOW("m1", "PVR"), SHOW("m2", "PVR")],
  },
};
const SEATS_SHOW = "77777777-7777-7777-7777-777777777777";

async function mockApi(page: Page) {
  await page.route("**/api/**", (route) => {
    const url = route.request().url();
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    const event = url.match(/\/api\/browse\/events\/([^/?]+)/);
    if (event) return json({ id: event[1], event_id: event[1], description: "x", ...EVENTS[event[1]] });
    if (/\/api\/seats\/[^/?]+\/map/.test(url)) {
      return json({
        layout_type: "cinema", stage_position: "front", zones: [], terms_and_conditions: "", terms_hash: "x",
        seats: [1, 2, 3].map((n) => ({ show_seat_id: `s${n}`, status: "available", price: 200, row_label: "A", seat_number: n, seat_type: "standard" })),
      });
    }
    const show = url.match(/\/api\/browse\/shows\/([^/?]+)/);
    if (show) return json({ id: show[1], show_id: show[1], title: "Dune", start_time: "2030-01-10T14:00:00Z" });
    return json([]);
  });
}

test.describe("Post-deploy UX fixes", () => {
  test.beforeEach(async ({ page }) => mockApi(page));

  test("customers don't see the internal event status", async ({ page }) => {
    await page.goto(`/events/${MOVIE}`);
    await expect(page.getByRole("heading", { name: "Dune", level: 1 })).toBeVisible();
    await expect(page.getByText(/Status:/)).toHaveCount(0);
  });

  test("live events talk about venues, movies about theatres", async ({ page }) => {
    await page.goto(`/events/${CONCERT}`);
    await expect(page.getByText(/In 2 Venues/)).toBeVisible();
    await expect(page.getByText(/Theatres/)).toHaveCount(0);

    await page.goto(`/events/${MOVIE}`);
    await expect(page.getByText(/In 1 Theatre \(/)).toBeVisible();
  });

  test("a guest gets no fake hold timer, only a prompt to log in", async ({ page }) => {
    await page.goto(`/shows/${SEATS_SHOW}/seats`);
    await page.locator("svg text", { hasText: /^1$/ }).first().click({ force: true });
    await expect(page.getByTestId("guest-hold-note")).toHaveText("Log in to hold these seats");
    await expect(page.getByText(/Hold Timer/)).toHaveCount(0);
    await expect(page.getByText(/Hold: \d/)).toHaveCount(0);
  });

  test("a cinema seat is not labelled Grandstand", async ({ page }) => {
    await page.goto(`/shows/${SEATS_SHOW}/seats`);
    await page.locator("svg text", { hasText: /^1$/ }).first().click({ force: true });
    await expect(page.getByText("Row A, Seat 1")).toBeVisible();
    await expect(page.getByText(/Grandstand/)).toHaveCount(0);
  });

  test("pages send basic security headers", async ({ page }) => {
    const response = await page.goto("/browse");
    const headers = response!.headers();
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  });
});
