import { test, expect, Page } from "@playwright/test";
import { loginWithMockFirebase } from "../helpers/mockAuth";

const CUSTOMER_PROFILE = {
  id: "33333333-3333-3333-3333-333333333333",
  name: "Alice Customer",
  email: "alice@ticketflow.test",
  roles: ["customer"],
  status: "active",
};

const BOOKING_ID = "99999999-9999-9999-9999-999999999991";

function mockBooking(status: "pending" | "confirmed") {
  return {
    id: BOOKING_ID,
    status,
    total_amount: 500,
    seats_info: [
      { row_label: "A", seat_number: 1, seat_type: "standard", price: 250 },
      { row_label: "A", seat_number: 2, seat_type: "standard", price: 250 },
    ],
  };
}

async function openPaymentFromBookings(page: Page) {
  await page.route("**/api/bookings", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: BOOKING_ID,
          status: "pending",
          total_amount: 500,
          event_title: "Interstellar",
          venue_name: "PVR Ahmedabad",
          city: "Ahmedabad",
          start_time: "2026-12-20T18:00:00Z",
          seat_count: 2,
        },
      ]),
    });
  });

  await page.getByRole("link", { name: "My Bookings" }).click();
  await expect(page).toHaveURL(/\/bookings$/, { timeout: 15_000 });
  await page.getByRole("link", { name: "Pay Now", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/payment\\?booking_id=${BOOKING_ID}$`), { timeout: 15_000 });
}

async function mockRazorpayCheckoutJs(page: Page, mode: "success" | "dismiss") {
  await page.route("https://checkout.razorpay.com/v1/checkout.js", async (route) => {
    const scriptBody =
      mode === "success"
        ? `window.Razorpay = function(opts) {
             return {
               open: function() {
                 opts.handler({
                   razorpay_order_id: opts.order_id,
                   razorpay_payment_id: "pay_Test987654",
                   razorpay_signature: "sig_valid_mock"
                 });
               }
             };
           };`
        : `window.Razorpay = function(opts) {
             return {
               open: function() {
                 if (opts.modal && opts.modal.ondismiss) opts.modal.ondismiss();
               }
             };
           };`;
    await route.fulfill({ status: 200, contentType: "application/javascript", body: scriptBody });
  });
}

test.describe("Payment Gateway - Basic UI", () => {
  test.beforeEach(async ({ page }) => {
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);
  });

  test("PAY-UI-01: payment page displays pending booking summary and Pay button", async ({ page }) => {
    await mockRazorpayCheckoutJs(page, "success");
    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockBooking("pending")),
      });
    });

    await openPaymentFromBookings(page);
    await expect(page.getByRole("heading", { name: "Complete Payment" })).toBeVisible();
    await expect(page.getByText("A1, A2")).toBeVisible();
    await expect(page.getByText("pending")).toBeVisible();
    await expect(page.getByText("₹500.00").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Pay ₹500.00" })).toBeVisible();
  });

  test("PAY-UI-02: clicking Pay creates order, verifies payment, generates ticket, and redirects to booking details", async ({ page }) => {
    let currentStatus: "pending" | "confirmed" = "pending";
    let confirmCalled = false;

    await mockRazorpayCheckoutJs(page, "success");

    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockBooking(currentStatus)),
      });
    });

    await page.route("**/api/payments/orders", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          razorpay_order_id: "order_Mock123",
          amount: 50000,
          currency: "INR",
          key_id: "rzp_test_mock",
          booking_id: BOOKING_ID,
        }),
      });
    });

    await page.route(`**/api/payments/orders/${BOOKING_ID}/verify`, async (route) => {
      currentStatus = "confirmed";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "success",
          booking_id: BOOKING_ID,
          receipt_number: "TF-99999999-987654",
        }),
      });
    });

    await page.route(`**/api/tickets/bookings/${BOOKING_ID}/confirm`, async (route) => {
      confirmCalled = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Ticket generated and emailed", ticket_id: "ticket-1" }),
      });
    });

    await openPaymentFromBookings(page);
    await page.getByRole("button", { name: "Pay ₹500.00" }).click();

    await expect(page.getByText("Payment successful! Ticket emailed to you.")).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/bookings/${BOOKING_ID}$`), { timeout: 15_000 });
    expect(confirmCalled).toBe(true);
  });

  test("PAY-UI-03: confirmed booking shows completed state and Download Ticket PDF button", async ({ page }) => {
    await mockRazorpayCheckoutJs(page, "success");
    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockBooking("confirmed")),
      });
    });

    await openPaymentFromBookings(page);
    await expect(page.getByText("Payment already completed!")).toBeVisible();
    await expect(page.getByRole("button", { name: "Download Ticket PDF" })).toBeVisible();
  });

  test("PAY-UI-04: confirmed payment page downloads ticket PDF cleanly", async ({ page }) => {
    await mockRazorpayCheckoutJs(page, "success");
    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockBooking("confirmed")),
      });
    });
    await page.route(`**/api/tickets/bookings/${BOOKING_ID}/pdf`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/pdf",
        body: Buffer.from("%PDF-1.4\n%MockPDF\n%%EOF"),
      });
    });

    await openPaymentFromBookings(page);
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download Ticket PDF" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(`ticket_${BOOKING_ID.slice(0, 8)}.pdf`);
    await expect(page.getByText("Ticket PDF downloaded")).toBeVisible();
  });
});
