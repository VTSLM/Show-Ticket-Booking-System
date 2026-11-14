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

const pendingBooking = {
  id: BOOKING_ID,
  status: "pending",
  total_amount: 500,
  seats_info: [{ row_label: "A", seat_number: 1, seat_type: "standard", price: 500 }],
};

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
          seat_count: 1,
        },
      ]),
    });
  });

  await page.getByRole("link", { name: "My Bookings" }).click();
  await expect(page).toHaveURL(/\/bookings$/, { timeout: 15_000 });
  await page.getByRole("link", { name: "Pay Now", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/payment\\?booking_id=${BOOKING_ID}$`), { timeout: 15_000 });
}

test.describe("Payment Gateway - Edge Cases", () => {
  test("PAY-EDGE-01: unauthenticated visitor sees login prompt on payment page", async ({ page }) => {
    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({ status: 401, contentType: "application/json", body: "{}" });
    });

    await page.goto(`/payment?booking_id=${BOOKING_ID}`);
    await expect(page.getByText(/Please log in to continue\./i)).toBeVisible();
    await expect(page.getByRole("link", { name: "log in" })).toHaveAttribute("href", "/auth/login");
  });

  test("PAY-EDGE-02: non-existent booking shows Booking not found state", async ({ page }) => {
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);
    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Booking not found" }),
      });
    });

    await openPaymentFromBookings(page);
    await expect(page.getByText("Booking not found.").first()).toBeVisible();
  });

  test("PAY-EDGE-03: dismissing Razorpay modal re-enables the Pay button", async ({ page }) => {
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);

    await page.route("https://checkout.razorpay.com/v1/checkout.js", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/javascript",
        body: `window.Razorpay = function(opts) {
          return { open: function() { opts.modal.ondismiss(); } };
        };`,
      });
    });
    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(pendingBooking) });
    });
    await page.route("**/api/payments/orders", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ razorpay_order_id: "order_Dismiss1", amount: 50000, currency: "INR", key_id: "rzp_test" }),
      });
    });

    await openPaymentFromBookings(page);
    const payBtn = page.getByRole("button", { name: "Pay ₹500.00" });
    await payBtn.click();

    await expect(payBtn).toBeEnabled();
  });

  test("PAY-EDGE-04: createOrder 400 error displays toast and recovers button state", async ({ page }) => {
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);

    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(pendingBooking) });
    });
    await page.route("**/api/payments/orders", async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Booking is confirmed, cannot pay" }),
      });
    });

    await openPaymentFromBookings(page);
    await page.getByRole("button", { name: "Pay ₹500.00" }).click();

    await expect(page.getByText("Booking is confirmed, cannot pay")).toBeVisible();
    await expect(page.getByRole("button", { name: "Pay ₹500.00" })).toBeEnabled();
  });

  test("PAY-EDGE-05: invalid payment signature shows error toast and stays on /payment", async ({ page }) => {
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);

    await page.route("https://checkout.razorpay.com/v1/checkout.js", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/javascript",
        body: `window.Razorpay = function(opts) {
          return {
            open: function() {
              opts.handler({
                razorpay_order_id: opts.order_id,
                razorpay_payment_id: "pay_Bad",
                razorpay_signature: "tampered_sig"
              });
            }
          };
        };`,
      });
    });
    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(pendingBooking) });
    });
    await page.route("**/api/payments/orders", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ razorpay_order_id: "order_Bad1", amount: 50000, currency: "INR", key_id: "rzp_test" }),
      });
    });
    await page.route(`**/api/payments/orders/${BOOKING_ID}/verify`, async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid payment signature" }),
      });
    });

    await openPaymentFromBookings(page);
    await page.getByRole("button", { name: "Pay ₹500.00" }).click();

    await expect(page.getByText("Invalid payment signature")).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/payment\\?booking_id=${BOOKING_ID}$`));
  });

  test("PAY-EDGE-06: direct navigation / refresh on /payment fails before AuthContext finishes loading (known DEF-PAY-05)", async ({ page }) => {
    test.fail(true, "Known defect DEF-PAY-05: payment/page.tsx fetches booking before useAuth() restores user.");
    await loginWithMockFirebase(page, CUSTOMER_PROFILE);
    await page.route(`**/api/bookings/${BOOKING_ID}`, async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(pendingBooking) });
    });

    await page.goto(`/payment?booking_id=${BOOKING_ID}`);
    await expect(page.getByRole("heading", { name: "Complete Payment" })).toBeVisible({ timeout: 5_000 });
  });
});
