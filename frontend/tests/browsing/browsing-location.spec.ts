import { test, expect } from "@playwright/test";

const indiaCities = [
  { name: "Ahmedabad", state: "Gujarat", lat: 23.0225, lng: 72.5714 },
  { name: "Mumbai", state: "Maharashtra", lat: 19.076, lng: 72.8777 },
  { name: "Delhi", state: "Delhi", lat: 28.6139, lng: 77.209 },
];

const mockShows = [
  {
    show_id: "show-nearby",
    start_time: "2026-12-15T18:30:00",
    base_price: 250,
    show_status: "scheduled",
    event_id: "event-nearby",
    title: "Nearby Movie",
    event_type: "movie",
    language: "English",
    genre: "Action",
    duration_minutes: 120,
    poster_url: null,
    venue_id: "venue-nearby",
    venue_name: "PVR Ahmedabad",
    city: "Ahmedabad",
    address: "SG Highway",
    screen_name: "Audi 1",
    capacity: 100,
    available_seats: 50,
    total_seats: 100,
    distance_km: 4.2,
    distance_exact: true,
  },
  {
    show_id: "show-concert",
    start_time: "2026-12-20T20:00:00",
    base_price: 1500,
    show_status: "scheduled",
    event_id: "event-concert",
    title: "National Concert",
    event_type: "concert",
    language: "Hindi",
    genre: "Rock",
    duration_minutes: 180,
    poster_url: null,
    venue_id: "venue-far",
    venue_name: "DY Patil Stadium",
    city: "Mumbai",
    address: "Nerul",
    screen_name: "Main Arena",
    capacity: 5000,
    available_seats: 1200,
    total_seats: 5000,
    distance_km: 440.0,
    distance_exact: true,
  },
];

test.describe("Location Picker & Nearby Browsing Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/browse/india-cities", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(indiaCities),
      });
    });

    await page.route("**/api/browse/shows*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockShows),
      });
    });
  });

  test("opens location picker, selects a city, and updates local state", async ({ page }) => {
    await page.goto("/browse");

    // Click location trigger in navbar or browse header
    const setLocBtn = page.getByRole("button", { name: /location/i }).first();
    await expect(setLocBtn).toBeVisible();
    await setLocBtn.click();

    // Verify modal dialog is visible
    const dialog = page.getByRole("dialog", { name: /choose your location/i });
    await expect(dialog).toBeVisible();

    // Search for a city
    const searchInput = page.getByRole("textbox", { name: /search city/i });
    await searchInput.fill("Ahmedabad");

    // Click the city from suggestions
    const cityOption = page.getByRole("button", { name: /Ahmedabad/i }).first();
    await expect(cityOption).toBeVisible();
    await cityOption.click();

    // Click confirmation button
    const confirmBtn = page.getByRole("button", { name: /show shows within/i });
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // Dialog should be closed
    await expect(dialog).not.toBeVisible();

    // Saved location should reflect in browse header or navbar
    await expect(page.getByText(/Ahmedabad/i).first()).toBeVisible();
  });

  test("displays distance badges on show cards when location is active", async ({ page }) => {
    // Seed location in localStorage
    await page.addInitScript(() => {
      localStorage.setItem(
        "ticketflow_location",
        JSON.stringify({
          lat: 23.0225,
          lng: 72.5714,
          label: "Ahmedabad",
          source: "city",
        })
      );
    });

    await page.goto("/browse");

    // The nearby movie badge should show distance
    await expect(page.getByText(/4\.2 km away/i)).toBeVisible();
  });
});
