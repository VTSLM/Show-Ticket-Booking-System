import { test, expect, Page } from "@playwright/test";

// #168: cinema formats only for movies, and a stage (never a screen) for live events.
// The API is mocked, so no backend is needed.
const SHOW = (id: string, screen: string) => ({
  show_id: id, id, start_time: "2030-01-10T14:00:00Z", screen_name: screen,
  venue_name: "Main Venue", venue_id: "v1", city: "Ahmedabad", base_price: 300,
});
const EVENTS: Record<string, any> = {
  "11111111-1111-1111-1111-111111111111": {
    title: "Dune", event_type: "movie", formats: ["2D"],
    upcoming_shows: [SHOW("a1", "Audi 1"), SHOW("a2", "IMAX Audi 2")],
  },
  "22222222-2222-2222-2222-222222222222": {
    title: "Stand-up Night", event_type: "other", formats: ["2D"],
    upcoming_shows: [SHOW("b1", "Audi 1"), SHOW("b2", "Audi 2")],
  },
};
const SEAT_MAPS: Record<string, string> = {
  "33333333-3333-3333-3333-333333333333": "cinema",
  "44444444-4444-4444-4444-444444444444": "stage",
};

async function mockApi(page: Page) {
  await page.route("**/api/**", (route) => {
    const url = route.request().url();
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    const event = url.match(/\/api\/browse\/events\/([^/?]+)/);
    if (event) return json({ id: event[1], event_id: event[1], description: "x", ...EVENTS[event[1]] });
    const map = url.match(/\/api\/seats\/([^/?]+)\/map/);
    if (map) {
      return json({
        layout_type: SEAT_MAPS[map[1]], stage_position: "front", zones: [], terms_and_conditions: "", terms_hash: "x",
        seats: [1, 2, 3, 4].map((n) => ({ show_seat_id: `s${n}`, status: "available", price: 200, row_label: "A", seat_number: n, seat_type: "standard" })),
      });
    }
    const show = url.match(/\/api\/browse\/shows\/([^/?]+)/);
    if (show) return json({ id: show[1], show_id: show[1], title: "Test show", start_time: "2030-01-10T14:00:00Z" });
    return json([]);
  });
}

test.describe("Event types (#168)", () => {
  test.beforeEach(async ({ page }) => mockApi(page));

  test("a live event shows no cinema formats and books without the format pop-up", async ({ page }) => {
    await page.goto("/events/22222222-2222-2222-2222-222222222222");
    await expect(page.getByRole("heading", { name: "Stand-up Night", level: 1 })).toBeVisible();
    for (const fmt of ["2D", "3D", "IMAX 3D", "4DX 3D"]) {
      await expect(page.getByText(fmt, { exact: true })).toHaveCount(0);
    }
    await page.getByRole("button", { name: /Book Tickets/ }).click();
    await expect(page.getByText("Select language and format")).toHaveCount(0);
  });

  test("a movie offers only the formats its showtimes have", async ({ page }) => {
    await page.goto("/events/11111111-1111-1111-1111-111111111111");
    await page.getByRole("button", { name: /Book Tickets/ }).click();
    const dialog = page.getByText("Select language and format").locator("..").locator("..");
    await expect(dialog.getByRole("button", { name: "2D", exact: true })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "IMAX 3D", exact: true })).toBeVisible();
    await expect(dialog.getByRole("button", { name: "4DX 3D", exact: true })).toHaveCount(0);
    await expect(dialog.getByRole("button", { name: "3D", exact: true })).toHaveCount(0);
  });

  test("the seat map draws a screen for a movie", async ({ page }) => {
    await page.goto("/shows/33333333-3333-3333-3333-333333333333/seats");
    await expect(page.getByText(/SCREEN THIS WAY/)).toBeVisible();
    await expect(page.getByText("🎤 STAGE")).toHaveCount(0);
  });

  test("the seat map draws a stage for a live event", async ({ page }) => {
    await page.goto("/shows/44444444-4444-4444-4444-444444444444/seats");
    await expect(page.getByText("🎤 STAGE")).toBeVisible();
    await expect(page.getByText(/SCREEN THIS WAY/)).toHaveCount(0);
  });
});
