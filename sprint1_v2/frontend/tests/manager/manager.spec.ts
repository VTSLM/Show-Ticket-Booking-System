import { test, expect, Page } from "@playwright/test";
import { loginWithMockFirebase } from "../helpers/mockAuth";

const MANAGER_PROFILE = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Test Manager",
  email: "manager@ticketflow.test",
  roles: ["manager"],
  status: "active",
};

function fieldControl(page: Page, labelText: string, tag: "input" | "select" = "input") {
  return page
    .locator("label", { hasText: new RegExp(`^${labelText}$`, "i") })
    .locator("..")
    .locator(tag);
}

async function setupManagerStatefulMocks(page: Page) {
  const venues = [
    { id: "venue-1", name: "PVR Ahmedabad", city: "Ahmedabad", address: "SG Highway" },
  ];
  const screensByVenue: Record<string, any[]> = {
    "venue-1": [
      { id: "screen-1", venue_id: "venue-1", name: "Audi 1", capacity: 60 },
    ],
  };
  const events = [
    {
      id: "event-1",
      title: "Interstellar",
      event_type: "movie",
      language: "English",
      duration_minutes: 165,
      status: "published",
    },
  ];
  let shows = [
    {
      id: "show-1",
      event_id: "event-1",
      screen_id: "screen-1",
      event_title: "Interstellar",
      venue_name: "PVR Ahmedabad",
      screen_name: "Audi 1",
      start_time: "2026-12-20T18:00:00Z",
      end_time: "2026-12-20T21:00:00Z",
      base_price: 250,
      status: "scheduled",
    },
  ];

  await page.route("**/api/manager/venues/*/screens", async (route) => {
    const url = route.request().url();
    const match = url.match(/\/api\/manager\/venues\/([^/]+)\/screens/);
    const venueId = match ? match[1] : "";

    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(screensByVenue[venueId] || []),
      });
      return;
    }

    const body = route.request().postDataJSON();
    const created = {
      id: `screen-${Date.now()}`,
      venue_id: venueId,
      name: body.name,
      capacity: body.capacity,
    };
    screensByVenue[venueId] = [...(screensByVenue[venueId] || []), created];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(created),
    });
  });

  await page.route("**/api/manager/venues", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(venues),
      });
      return;
    }

    const body = route.request().postDataJSON();
    const created = {
      id: `venue-${venues.length + 1}`,
      name: body.name,
      city: body.city,
      address: body.address || "",
    };
    venues.push(created);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(created),
    });
  });

  await page.route("**/api/manager/events", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(events),
      });
      return;
    }

    const body = route.request().postDataJSON();
    const created = {
      id: `event-${events.length + 1}`,
      title: body.title,
      event_type: body.event_type || "movie",
      language: body.language || "",
      duration_minutes: body.duration_minutes || 120,
      status: body.status || "draft",
    };
    events.unshift(created);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(created),
    });
  });

  await page.route("**/api/manager/shows/*", async (route) => {
    if (route.request().method() === "DELETE") {
      const showId = route.request().url().split("/").pop();
      shows = shows.filter((s) => s.id !== showId);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Show deleted" }),
      });
      return;
    }
    await route.continue();
  });

  await page.route("**/api/manager/shows", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(shows),
      });
      return;
    }

    const body = route.request().postDataJSON();
    const ev = events.find((e) => e.id === body.event_id);
    const allScreens = Object.values(screensByVenue).flat();
    const sc = allScreens.find((s) => s.id === body.screen_id);
    const vn = venues.find((v) => v.id === sc?.venue_id);
    const created = {
      id: `show-${shows.length + 1}`,
      event_id: body.event_id,
      screen_id: body.screen_id,
      event_title: ev?.title || "Show",
      venue_name: vn?.name || "Venue",
      screen_name: sc?.name || "Screen",
      start_time: body.start_time,
      end_time: body.end_time,
      base_price: body.base_price,
      status: "scheduled",
    };
    shows = [created, ...shows];
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(created),
    });
  });
}

test.describe("Manager Listing - Basic UI", () => {
  test.beforeEach(async ({ page }) => {
    await setupManagerStatefulMocks(page);
    await loginWithMockFirebase(page, MANAGER_PROFILE);
    await page.getByRole("link", { name: "Manager", exact: true }).click();
    await expect(page).toHaveURL(/\/manager$/, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: "Manager Dashboard" })).toBeVisible();
  });

  test("MGR-UI-01: manager dashboard loads tabs and existing shows", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Shows" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Events" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Venues" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Create Show" })).toBeVisible();
    await expect(page.getByText("All Shows (1)")).toBeVisible();
    await expect(page.getByText("PVR Ahmedabad — Audi 1")).toBeVisible();
  });

  test("MGR-UI-02: selecting a venue loads its screens into the Create Show dropdown", async ({ page }) => {
    const screenSelect = fieldControl(page, "Screen", "select");
    await expect(screenSelect).toBeDisabled();

    await fieldControl(page, "Venue", "select").selectOption("venue-1");
    await expect(screenSelect).toBeEnabled();
    await expect(screenSelect).toContainText("Audi 1 (60 seats)");
  });

  test("MGR-UI-03: manager can create a venue", async ({ page }) => {
    await page.getByRole("button", { name: "Venues" }).click();
    await expect(page.getByRole("heading", { name: "Create Venue" })).toBeVisible();

    await fieldControl(page, "Name").fill("Cinepolis Nexus");
    await fieldControl(page, "City").fill("Ahmedabad");
    await fieldControl(page, "Address").fill("Vastrapur");
    await page.getByRole("button", { name: "Create Venue" }).click();

    await expect(page.getByText("Venue created!")).toBeVisible();
    await expect(page.getByText("Cinepolis Nexus", { exact: true })).toBeVisible();
    await expect(page.getByText("Venues (2)")).toBeVisible();
  });

  test("MGR-UI-04: manager can create a screen with rows and columns", async ({ page }) => {
    await page.getByRole("button", { name: "Venues" }).click();
    await fieldControl(page, "Select Venue", "select").selectOption("venue-1");

    await fieldControl(page, "Screen Name").fill("IMAX Hall");
    await fieldControl(page, "Rows").fill("2");
    await fieldControl(page, "Columns").fill("10");
    await expect(page.getByText("20 seats")).toBeVisible();

    await page.getByRole("button", { name: "Create Screen" }).click();

    await expect(page.getByText("Screen created with 20 seats!")).toBeVisible();
    await expect(page.getByText("IMAX Hall")).toBeVisible();
  });

  test("MGR-UI-05: manager can create an event", async ({ page }) => {
    await page.getByRole("button", { name: "Events" }).click();
    await expect(page.getByRole("heading", { name: "Create Event" })).toBeVisible();

    await fieldControl(page, "Title").fill("Inception");
    await fieldControl(page, "Type", "select").selectOption("movie");
    await fieldControl(page, "Language").fill("English");
    await fieldControl(page, "Duration \\(min\\)").fill("148");
    await page.getByRole("button", { name: "Create Event" }).click();

    await expect(page.getByText("Event created!")).toBeVisible();
    await expect(page.getByText("Inception")).toBeVisible();
  });

  test("MGR-UI-06: manager can schedule a show with auto-calculated end time", async ({ page }) => {
    await fieldControl(page, "Event", "select").selectOption("event-1");
    await fieldControl(page, "Venue", "select").selectOption("venue-1");
    await fieldControl(page, "Screen", "select").selectOption("screen-1");
    await fieldControl(page, "Base Price \\(₹\\)").fill("420");
    await fieldControl(page, "Start Time").fill("2026-12-25T18:00");

    const endTimeInput = fieldControl(page, "End Time");
    await expect(endTimeInput).not.toHaveValue("");

    await page.getByRole("button", { name: "Create Show" }).click();
    await expect(page.getByText("Show created!")).toBeVisible();
    await expect(page.getByText("All Shows (2)")).toBeVisible();
  });

  test("MGR-UI-07: manager can delete an existing show", async ({ page }) => {
    page.on("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Delete" }).first().click();

    await expect(page.getByText("Deleted")).toBeVisible();
    await expect(page.getByText("All Shows (0)")).toBeVisible();
  });
});

