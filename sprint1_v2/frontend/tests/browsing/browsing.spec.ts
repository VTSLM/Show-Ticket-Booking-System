import { test, expect } from "@playwright/test";

const shows = [
  {
    show_id: "show-101",
    start_time: "2026-12-15T18:30:00",
    base_price: 250,
    show_status: "scheduled",
    event_id: "event-101",
    title: "Interstellar",
    event_type: "movie",
    language: "English",
    genre: "Sci-Fi",
    duration_minutes: 169,
    poster_url: null,
    description: "A science-fiction movie.",
    venue_id: "venue-101",
    venue_name: "PVR Ahmedabad",
    city: "Ahmedabad",
    address: "SG Highway",
    screen_name: "Audi 1",
    capacity: 100,
    available_seats: 72,
    total_seats: 100,
  },
  {
    show_id: "show-102",
    start_time: "2026-12-16T19:00:00",
    base_price: 350,
    show_status: "scheduled",
    event_id: "event-102",
    title: "Coldplay Live",
    event_type: "concert",
    language: "English",
    genre: "Music",
    duration_minutes: 120,
    poster_url: null,
    description: "Live concert.",
    venue_id: "venue-102",
    venue_name: "Narendra Modi Stadium",
    city: "Ahmedabad",
    screen_name: "Main",
    capacity: 500,
    available_seats: 250,
    total_seats: 500,
  },
];

const cities = ["Ahmedabad", "Mumbai", "Delhi"];

async function mockBrowseApi(page: any) {
  await page.route("**/api/browse/cities", async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(cities),
    });
  });

  await page.route("**/api/browse/shows**", async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(shows),
    });
  });
}

test.describe("Browsing - Basic UI", () => {
  test.beforeEach(async ({ page }) => {
    await mockBrowseApi(page);
    await page.goto("/browse");
  });

  test("BROWSE-UI-01 browse page loads successfully", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Movies & Shows" })
    ).toBeVisible();

    await expect(
      page.getByText("Discover what’s playing near you.")
    ).toBeVisible();
  });

  test("BROWSE-UI-02 search controls are visible", async ({ page }) => {
    await expect(
      page.getByRole("textbox", { name: "Search shows or venues" })
    ).toBeVisible();

    await expect(
      page.getByRole("combobox", { name: "Filter by city" })
    ).toBeVisible();

    await expect(
      page.getByRole("combobox", { name: "Filter by show type" })
    ).toBeVisible();

    await expect(
      page.getByRole("button", { name: "Search" })
    ).toBeVisible();
  });

  test("BROWSE-UI-03 shows are displayed", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Interstellar" })
    ).toBeVisible();

    await expect(
      page.getByRole("heading", { name: "Coldplay Live" })
    ).toBeVisible();
  });

  test("BROWSE-UI-04 show information is displayed", async ({ page }) => {
    const interstellarCard = page.getByRole("link", {
        name: /Interstellar movie English/i,
    });

    await expect(interstellarCard).toBeVisible();

    await expect(interstellarCard).toContainText("PVR Ahmedabad");
    await expect(interstellarCard).toContainText("Ahmedabad");
    await expect(interstellarCard).toContainText("English");
    await expect(interstellarCard).toContainText("₹250");
    await expect(interstellarCard).toContainText("72 seats");
    });

  test("BROWSE-UI-05 city options are loaded", async ({ page }) => {
    const citySelect = page.getByRole("combobox", {
      name: "Filter by city",
    });

    await expect(citySelect).toContainText("Ahmedabad");
    await expect(citySelect).toContainText("Mumbai");
    await expect(citySelect).toContainText("Delhi");
  });

  test("BROWSE-UI-06 clicking a show opens seat selection", async ({
    page,
  }) => {
    const showLink = page
      .getByRole("heading", { name: "Interstellar" })
      .locator("..")
      .locator("..")
      .locator("..");

    await showLink.click();

    await expect(page).toHaveURL(/\/shows\/show-101\/seats$/);
  });
});