import { test, expect, Page } from "@playwright/test";
import { loginWithMockFirebase } from "../helpers/mockAuth";

const MANAGER_PROFILE = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Test Manager",
  email: "manager@ticketflow.test",
  roles: ["manager"],
  status: "active",
};

const CUSTOMER_PROFILE = {
  id: "22222222-2222-2222-2222-222222222222",
  name: "Test Customer",
  email: "customer@ticketflow.test",
  roles: ["customer"],
  status: "active",
};

function fieldControl(page: Page, labelText: string, tag: "input" | "select" = "input") {
  return page
    .locator("label", { hasText: new RegExp(`^${labelText}$`, "i") })
    .locator("..")
    .locator(tag);
}

async function setupBaseManagerMocks(page: Page) {
  await page.route("**/api/manager/venues/*/screens", async (route) => {
    const url = route.request().url();
    if (url.includes("venue-empty")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{ id: "screen-1", venue_id: "venue-1", name: "Audi 1", capacity: 60 }]),
    });
  });

  await page.route("**/api/manager/venues", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { id: "venue-1", name: "PVR Ahmedabad", city: "Ahmedabad" },
        { id: "venue-empty", name: "Empty Cinema", city: "Surat" },
      ]),
    });
  });

  await page.route("**/api/manager/events", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { id: "event-1", title: "Interstellar", event_type: "movie", duration_minutes: 165, status: "published" },
      ]),
    });
  });

  await page.route("**/api/manager/shows", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "show-booked",
            event_title: "Interstellar",
            venue_name: "PVR Ahmedabad",
            screen_name: "Audi 1",
            start_time: "2026-12-20T18:00:00Z",
            end_time: "2026-12-20T21:00:00Z",
            base_price: 250,
          },
        ]),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
}

test.describe("Manager Listing - Edge Cases", () => {
  test("MGR-EDGE-01: rejects show when end time is before start time client-side", async ({ page }) => {
    await setupBaseManagerMocks(page);
    await loginWithMockFirebase(page, MANAGER_PROFILE);
    await page.getByRole("link", { name: "Manager", exact: true }).click();
    await expect(page).toHaveURL(/\/manager$/);

    let postCalled = false;
    await page.route("**/api/manager/shows", async (route) => {
      if (route.request().method() === "POST") {
        postCalled = true;
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await fieldControl(page, "Event", "select").selectOption("event-1");
    await fieldControl(page, "Venue", "select").selectOption("venue-1");
    await fieldControl(page, "Screen", "select").selectOption("screen-1");
    await fieldControl(page, "Base Price \\(₹\\)").fill("300");
    await fieldControl(page, "Start Time").fill("2026-12-25T18:00");
    await fieldControl(page, "End Time").fill("2026-12-25T15:00");

    await expect(page.getByText("Show end time must be strictly after start time.")).toBeVisible();
    await page.getByRole("button", { name: "Create Show" }).click();

    expect(postCalled).toBe(false);
  });

  test("MGR-EDGE-02: displays conflict toast when backend returns 409 for overlapping show", async ({ page }) => {
    await setupBaseManagerMocks(page);
    await loginWithMockFirebase(page, MANAGER_PROFILE);
    await page.getByRole("link", { name: "Manager", exact: true }).click();
    await expect(page).toHaveURL(/\/manager$/);

    await page.route("**/api/manager/shows", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "Scheduling conflict on 'PVR Ahmedabad — Audi 1': overlaps with 'Interstellar'.",
          }),
        });
        return;
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await fieldControl(page, "Event", "select").selectOption("event-1");
    await fieldControl(page, "Venue", "select").selectOption("venue-1");
    await fieldControl(page, "Screen", "select").selectOption("screen-1");
    await fieldControl(page, "Base Price \\(₹\\)").fill("300");
    await fieldControl(page, "Start Time").fill("2026-12-20T18:30");

    await page.getByRole("button", { name: "Create Show" }).click();
    await expect(page.getByText(/Scheduling conflict on/i)).toBeVisible();
  });

  test("MGR-EDGE-03: venue with zero screens shows empty screen placeholder", async ({ page }) => {
    await setupBaseManagerMocks(page);
    await loginWithMockFirebase(page, MANAGER_PROFILE);
    await page.getByRole("link", { name: "Manager", exact: true }).click();
    await expect(page).toHaveURL(/\/manager$/);

    await fieldControl(page, "Venue", "select").selectOption("venue-empty");
    await expect(fieldControl(page, "Screen", "select")).toContainText("No screens in this venue");
  });

  test("MGR-EDGE-04: deleting a show with bookings displays 409 error without removing row", async ({ page }) => {
    await setupBaseManagerMocks(page);
    await loginWithMockFirebase(page, MANAGER_PROFILE);
    await page.getByRole("link", { name: "Manager", exact: true }).click();
    await expect(page).toHaveURL(/\/manager$/);

    await page.route("**/api/manager/shows/*", async (route) => {
      if (route.request().method() === "DELETE") {
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            detail: "Cannot delete this show because bookings already exist for it.",
          }),
        });
        return;
      }
      await route.continue();
    });

    page.on("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: "Delete" }).first().click();

    await expect(page.getByText(/bookings already exist/i)).toBeVisible();
    await expect(page.getByText("All Shows (1)")).toBeVisible();
  });

  test("MGR-EDGE-05: rejects screen creation if rows/columns <= 0", async ({ page }) => {
    await setupBaseManagerMocks(page);
    await loginWithMockFirebase(page, MANAGER_PROFILE);
    await page.getByRole("link", { name: "Manager", exact: true }).click();
    await expect(page).toHaveURL(/\/manager$/);

    await page.getByRole("button", { name: "Venues" }).click();
    await fieldControl(page, "Select Venue", "select").selectOption("venue-1");
    await fieldControl(page, "Screen Name").fill("Bad Screen");
    await fieldControl(page, "Rows").fill("0");
    await fieldControl(page, "Columns").fill("10");

    await page.getByRole("button", { name: "Create Screen" }).click();
    await expect(page.getByText("Rows and columns must be greater than 0")).toBeVisible();
  });

  test("MGR-EDGE-06: customer account cannot access /manager and is redirected home", async ({ page }) => {
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);
    await page.goto("/manager");
    await expect(page).toHaveURL(/\/$/, { timeout: 10_000 });
  });
});

