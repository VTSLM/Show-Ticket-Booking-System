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
const PENDING_ID = "88888888-8888-8888-8888-888888888882";

test.describe("Ticket Generation & Bookings - Basic UI", () => {
  test.beforeEach(async ({ page }) => {
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);
  });

  test("TICKET-UI-01: My Bookings renders confirmed and pending bookings", async ({ page }) => {
    await page.route("**/api/bookings", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: CONFIRMED_ID,
            status: "confirmed",
            total_amount: 500,
            event_title: "Interstellar",
            venue_name: "PVR Ahmedabad",
            city: "Ahmedabad",
            start_time: "2026-12-20T18:00:00Z",
            seat_count: 2,
          },
          {
            id: PENDING_ID,
            status: "pending",
            total_amount: 250,
            event_title: "Dune 2",
            venue_name: "Cinepolis",
            city: "Ahmedabad",
            start_time: "2026-12-22T20:00:00Z",
            seat_count: 1,
          },
        ]),
      });
    });

    await page.getByRole("link", { name: "My Bookings" }).click();
    await expect(page).toHaveURL(/\/bookings$/);
    await expect(page.getByRole("heading", { name: "My Bookings" })).toBeVisible();
    await expect(page.getByText("Interstellar")).toBeVisible();
    await expect(page.getByText("2 seat(s)")).toBeVisible();
    await expect(page.getByRole("link", { name: "Pay Now", exact: true })).toHaveAttribute(
      "href",
      `/payment?booking_id=${PENDING_ID}`
    );
  });

  test("TICKET-UI-02: confirmed booking detail page shows ticket download controls", async ({ page }) => {
    await page.route(`**/api/bookings/${CONFIRMED_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: CONFIRMED_ID,
          status: "confirmed",
          total_amount: 500,
          seats_info: [
            { row_label: "A", seat_number: 1, price: 250 },
            { row_label: "A", seat_number: 2, price: 250 },
          ],
        }),
      });
    });

    await page.goto(`/bookings/${CONFIRMED_ID}`);
    await expect(page.getByRole("heading", { name: "Booking Details" })).toBeVisible();
    await expect(page.getByText("CONFIRMED")).toBeVisible();
    await expect(page.getByText("A1, A2")).toBeVisible();
    await expect(page.getByText("₹500.00")).toBeVisible();
    await expect(page.getByRole("button", { name: "Download Ticket PDF" })).toBeVisible();
    await expect(page.getByText("Ticket sent to your email!")).toBeVisible();
  });

  test("TICKET-UI-03: clicking Download Ticket PDF requests /pdf with Bearer token and downloads file", async ({ page }) => {
    let seenAuthHeader = "";

    await page.route(`**/api/bookings/${CONFIRMED_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: CONFIRMED_ID,
          status: "confirmed",
          total_amount: 500,
          seats_info: [{ row_label: "A", seat_number: 1, price: 500 }],
        }),
      });
    });

    await page.route(`**/api/tickets/bookings/${CONFIRMED_ID}/pdf`, async (route) => {
      seenAuthHeader = route.request().headers()["authorization"] || "";
      await route.fulfill({
        status: 200,
        contentType: "application/pdf",
        body: Buffer.from("%PDF-1.4\n%TicketFlow\n%%EOF"),
      });
    });

    await page.goto(`/bookings/${CONFIRMED_ID}`);
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download Ticket PDF" }).click();
    const download = await downloadPromise;

    expect(seenAuthHeader).toMatch(/^Bearer .+/);
    expect(download.suggestedFilename()).toBe(`ticket_${CONFIRMED_ID.slice(0, 8)}.pdf`);
    await expect(page.getByText("Ticket PDF downloaded")).toBeVisible();
  });

  test("TICKET-UI-04: pending booking detail page shows Complete Payment link instead of PDF button", async ({ page }) => {
    await page.route(`**/api/bookings/${PENDING_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: PENDING_ID,
          status: "pending",
          total_amount: 250,
          seats_info: [{ row_label: "B", seat_number: 4, price: 250 }],
        }),
      });
    });

    await page.goto(`/bookings/${PENDING_ID}`);
    await expect(page.getByText("PENDING")).toBeVisible();
    await expect(page.getByRole("link", { name: "Complete Payment" })).toHaveAttribute(
      "href",
      `/payment?booking_id=${PENDING_ID}`
    );
    await expect(page.getByRole("button", { name: "Download Ticket PDF" })).not.toBeVisible();
  });
});

