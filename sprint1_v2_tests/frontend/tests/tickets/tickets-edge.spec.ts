import { test, expect } from "@playwright/test";
import { loginWithMockFirebase } from "../helpers/mockAuth";

const CUSTOMER_PROFILE = {
  id: "33333333-3333-3333-3333-333333333333",
  name: "Alice Customer",
  email: "alice@ticketflow.test",
  roles: ["customer"],
  status: "active",
};

const CONFIRMED_ID = "88888888-8888-8888-8888-888888888881";

test.describe("Ticket Generation & Bookings - Edge Cases", () => {
  test.beforeEach(async ({ page }) => {
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);
  });

  test("TICKET-EDGE-01: empty bookings list displays Browse Shows CTA", async ({ page }) => {
    await page.route("**/api/bookings", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });

    await page.getByRole("link", { name: "My Bookings" }).click();
    await expect(page.getByText("No bookings yet.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Browse Shows" }).last()).toHaveAttribute("href", "/browse");
  });

  test("TICKET-EDGE-02: missing booking renders Booking not found fallback", async ({ page }) => {
    await page.route(`**/api/bookings/${CONFIRMED_ID}`, async (route) => {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Booking not found" }) });
    });

    await page.goto(`/bookings/${CONFIRMED_ID}`);
    await expect(page.getByText("Booking not found.").first()).toBeVisible();
  });

  test("TICKET-EDGE-03: 404 from /pdf displays Ticket not found toast", async ({ page }) => {
    await page.route(`**/api/bookings/${CONFIRMED_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: CONFIRMED_ID, status: "confirmed", total_amount: 500, seats_info: [] }),
      });
    });
    await page.route(`**/api/tickets/bookings/${CONFIRMED_ID}/pdf`, async (route) => {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Not found" }) });
    });

    await page.goto(`/bookings/${CONFIRMED_ID}`);
    await page.getByRole("button", { name: "Download Ticket PDF" }).click();
    await expect(page.getByText("Ticket not found.")).toBeVisible();
  });

  test("TICKET-EDGE-04: 403 from /pdf displays authentication failure toast", async ({ page }) => {
    await page.route(`**/api/bookings/${CONFIRMED_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: CONFIRMED_ID, status: "confirmed", total_amount: 500, seats_info: [] }),
      });
    });
    await page.route(`**/api/tickets/bookings/${CONFIRMED_ID}/pdf`, async (route) => {
      await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Forbidden" }) });
    });

    await page.goto(`/bookings/${CONFIRMED_ID}`);
    await page.getByRole("button", { name: "Download Ticket PDF" }).click();
    await expect(page.getByText("Authentication failed. Please log in again.")).toBeVisible();
  });

  test("TICKET-EDGE-05: 500 from /pdf shows generic error toast and re-enables button", async ({ page }) => {
    await page.route(`**/api/bookings/${CONFIRMED_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: CONFIRMED_ID, status: "confirmed", total_amount: 500, seats_info: [] }),
      });
    });
    await page.route(`**/api/tickets/bookings/${CONFIRMED_ID}/pdf`, async (route) => {
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "PDF error" }) });
    });

    await page.goto(`/bookings/${CONFIRMED_ID}`);
    await page.getByRole("button", { name: "Download Ticket PDF" }).click();

    await expect(page.getByText("Could not download ticket PDF")).toBeVisible();
    await expect(page.getByRole("button", { name: "Download Ticket PDF" })).toBeEnabled();
  });
});

