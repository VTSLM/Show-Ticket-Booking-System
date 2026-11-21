import { test, expect, Page } from "@playwright/test";

// Event page city picker: stays inside its card and starts on the user's own city. API is mocked.
const EVENT = "88888888-8888-8888-8888-888888888888";
const CITIES = ["Vadodara", "Delhi", "Kolkata", "Chennai", "Bengaluru", "Pune", "Hyderabad", "Mumbai", "Ahmedabad", "Gandhinagar"];
const SHOWS = CITIES.map((city, i) => ({
  show_id: `s${i}`, id: `s${i}`, start_time: "2030-01-10T14:00:00Z", screen_name: "Audi 1",
  venue_name: `${city} Cinema`, venue_id: `v${i}`, city, base_price: 200,
}));

async function open(page: Page, query = "") {
  await page.addInitScript(() => {
    localStorage.setItem("ticketflow_location", JSON.stringify({ lat: 19.07, lng: 72.88, label: "Mumbai", source: "city" }));
  });
  await page.route("**/api/**", (route) => {
    const url = route.request().url();
    const body = /\/api\/browse\/events\//.test(url)
      ? { id: EVENT, event_id: EVENT, title: "3 Idiots", event_type: "movie", status: "published", language: "Hindi", upcoming_shows: SHOWS }
      : [];
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto(`/events/${EVENT}${query}`);
  await expect(page.getByTestId("city-picker")).toBeVisible();
}

test("starts on the user's city and lists it first", async ({ page }) => {
  await open(page);
  const buttons = page.getByTestId("city-picker").getByRole("button");
  await expect(buttons.first()).toHaveText(/Mumbai/);
  await expect(page.getByTestId("city-picker").getByRole("button", { name: /Mumbai/ })).toHaveAttribute("aria-pressed", "true");
});

test("a show picked earlier keeps its own city", async ({ page }) => {
  await open(page, "?show_id=s3");
  await expect(page.getByTestId("city-picker").getByRole("button", { name: /Chennai/ })).toHaveAttribute("aria-pressed", "true");
});

test("city buttons stay inside the card on one line each", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await open(page);
  const card = await page.locator("#showtimes-section").boundingBox();
  const picker = await page.getByTestId("city-picker").boundingBox();
  expect(picker!.x + picker!.width).toBeLessThanOrEqual(card!.x + card!.width);
  const btn = await page.getByTestId("city-picker").getByRole("button", { name: /Gandhinagar/ }).boundingBox();
  expect(btn!.height).toBeLessThan(40); // pin and name on one line
});
