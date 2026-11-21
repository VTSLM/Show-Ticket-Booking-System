import { test, expect, Page } from "@playwright/test";

// #170: an event without a working poster shows a neutral placeholder,
// never another event's poster. The event API is mocked, so no backend is needed.
const EVENTS: Record<string, { title: string; event_type: string; poster_url: string | null }> = {
  "11111111-1111-1111-1111-111111111111": { title: "Arijit Live", event_type: "concert", poster_url: null },
  "22222222-2222-2222-2222-222222222222": { title: "Stand-up Night", event_type: "comedy", poster_url: "https://example.invalid/broken.jpg" },
  "33333333-3333-3333-3333-333333333333": { title: "Ramayana", event_type: "theatre", poster_url: "/posters/ramayana.jpg" },
};

async function mockApi(page: Page) {
  await page.route("**/api/**", (route) => {
    const url = route.request().url();
    const match = url.match(/\/api\/browse\/events\/([^/?]+)/);
    if (!match) return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    const id = match[1];
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id, event_id: id, description: "x", upcoming_shows: [], ...EVENTS[id] }),
    });
  });
}

test.describe("Poster fallback (#170)", () => {
  test.beforeEach(async ({ page }) => mockApi(page));

  test("missing poster shows a placeholder for the event type", async ({ page }) => {
    await page.goto("/events/11111111-1111-1111-1111-111111111111");
    const placeholder = page.getByRole("img", { name: "Arijit Live poster (no poster available)" });
    await expect(placeholder).toBeVisible();
    await expect(placeholder).toContainText("🎵");
    await expect(page.locator('img[src*="ramayana"]')).toHaveCount(0);
  });

  test("broken poster URL falls back to the placeholder", async ({ page }) => {
    await page.goto("/events/22222222-2222-2222-2222-222222222222");
    await expect(page.getByRole("img", { name: "Stand-up Night poster (no poster available)" })).toBeVisible();
    await expect(page.locator('img[src*="ramayana"]')).toHaveCount(0);
  });

  test("a working poster is still shown", async ({ page }) => {
    await page.goto("/events/33333333-3333-3333-3333-333333333333");
    await expect(page.getByRole("img", { name: "Ramayana poster" })).toBeVisible();
  });
});
