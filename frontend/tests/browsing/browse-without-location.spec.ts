import { test, expect, Page } from "@playwright/test";

// #203: before a location is chosen, Browse listed only concerts. Now it lists every kind of
// show from every city, with a banner to set a location. The API is mocked.

const show = (id: string, type: string, title: string, city: string) => ({
  show_id: id, event_id: `event-${id}`, start_time: "2030-01-10T18:30:00", base_price: 250,
  show_status: "scheduled", title, event_type: type, language: "English", genre: "Drama",
  duration_minutes: 120, poster_url: null, venue_id: `venue-${id}`, venue_name: `${city} Venue`,
  city, address: "", screen_name: "Audi 1", capacity: 100, available_seats: 50, total_seats: 100,
});
const ALL = [
  show("m", "movie", "Dune: Part Two", "Mumbai"),
  show("c", "concert", "Neon Skyline Tour", "Delhi"),
  show("t", "theatre", "Hamlet, Retold", "Pune"),
  show("o", "other", "Pottery for Beginners", "Chennai"),
];

async function mock(page: Page) {
  const requests: URL[] = [];
  await page.route("**/api/browse/india-cities", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ name: "Mumbai", state: "Maharashtra", lat: 19.076, lng: 72.8777 }]) }));
  await page.route("**/api/browse/shows*", (route) => {
    const url = new URL(route.request().url());
    requests.push(url);
    const type = url.searchParams.get("event_type");
    const body = type ? ALL.filter((s) => s.event_type === type) : ALL;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  return requests;
}

test("without a location every kind of show is listed, from every city", async ({ page }) => {
  const requests = await mock(page);
  await page.goto("/browse");

  await expect(page.getByTestId("set-location-banner")).toBeVisible();
  for (const title of ["Dune: Part Two", "Neon Skyline Tour", "Hamlet, Retold", "Pottery for Beginners"]) {
    await expect(page.getByText(title).first()).toBeVisible();
  }
  // Rows don't claim "near you" when no location is known
  await expect(page.getByText("🎬 Movies", { exact: true })).toBeVisible();
  await expect(page.getByText(/near you/i)).toHaveCount(0);

  // The listing asks for everything: no concert-only filter, no radius
  const listing = requests.find((u) => !u.searchParams.has("search"))!;
  expect(listing.searchParams.get("event_type")).toBeNull();
  expect(listing.searchParams.has("lat")).toBe(false);
});

test("without a location a non-concert type filter still shows results", async ({ page }) => {
  const requests = await mock(page);
  await page.goto("/browse");
  await page.getByRole("button", { name: "🎬 Movies" }).first().click();
  await expect(page.getByText("Dune: Part Two").first()).toBeVisible();
  await expect(page.getByText("Neon Skyline Tour")).toHaveCount(0);
  expect(requests.some((u) => u.searchParams.get("event_type") === "movie")).toBe(true);
});

test("with a location the listing is still limited to nearby shows", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("ticketflow_location", JSON.stringify({ lat: 19.076, lng: 72.8777, label: "Mumbai", source: "city" }));
  });
  const requests = await mock(page);
  await page.goto("/browse");
  await expect(page.getByText("Dune: Part Two").first()).toBeVisible();
  await expect(page.getByTestId("set-location-banner")).toHaveCount(0);
  const listing = requests.find((u) => u.searchParams.has("lat"))!;
  expect(listing.searchParams.get("radius_km")).toBe("100");
});
