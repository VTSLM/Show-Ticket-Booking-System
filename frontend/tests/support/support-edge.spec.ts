import { test, expect } from "@playwright/test";

const SUPPORT_REQUEST_ID = "support-edge-123";

async function loginAsTestUser(page: any) {
  const email = process.env.TEST_LOGIN_EMAIL;
  const password = process.env.TEST_LOGIN_PASSWORD;

  if (!email || !password) {
    throw new Error(
      "TEST_LOGIN_EMAIL and TEST_LOGIN_PASSWORD must be set"
    );
  }

  await page.goto("/auth/login");

  await page.getByLabel(/email/i).fill(email);
  await page.locator("#password").fill(password);

  await page.getByRole("button", {
    name: /log\s*in|sign\s*in/i,
  }).click();

  await expect(page).toHaveURL(/\/browse/, {
    timeout: 15_000,
  });

  await page.waitForTimeout(1500);
}


// ---------------------------------------------------------------------------
// SUPPORT-EDGE-01
// ---------------------------------------------------------------------------

test("SUPPORT-EDGE-01: unauthenticated user is redirected from support page", async ({
  page,
}) => {
  await page.goto("/support");

  await expect(page).toHaveURL(/\/auth\/login/, {
    timeout: 10_000,
  });
});


// ---------------------------------------------------------------------------
// SUPPORT-EDGE-02
// ---------------------------------------------------------------------------

test("SUPPORT-EDGE-02: unauthenticated user is redirected from new request page", async ({
  page,
}) => {
  await page.goto("/support/new");

  await expect(page).toHaveURL(/\/auth\/login/, {
    timeout: 10_000,
  });
});


// ---------------------------------------------------------------------------
// SUPPORT-EDGE-03
// ---------------------------------------------------------------------------

test("SUPPORT-EDGE-03: invalid support request displays not found state", async ({
  page,
}) => {
  await loginAsTestUser(page);

  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}`,
    async route => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          detail: "Support request not found",
        }),
      });
    }
  );

  await page.goto(`/support/${SUPPORT_REQUEST_ID}`);

  await expect(
    page.getByText("Support request not found.")
  ).toBeVisible();

  await expect(
    page.getByRole("link", { name: "My Requests" })
  ).toBeVisible();
});


// ---------------------------------------------------------------------------
// SUPPORT-EDGE-04
// ---------------------------------------------------------------------------

test("SUPPORT-EDGE-04: subject below minimum length is rejected", async ({
  page,
}) => {
  await loginAsTestUser(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("account");

  await page.locator("#subject").fill("Help");

  await page
    .locator("#message")
    .fill("I cannot log into my account.");

  await page.getByRole("button", { name: /send request/i }).click();

  await expect(
    page.getByText("Subject must be at least 5 characters.")
  ).toBeVisible();
});


// ---------------------------------------------------------------------------
// SUPPORT-EDGE-05
// ---------------------------------------------------------------------------

test("SUPPORT-EDGE-05: message below minimum length is rejected", async ({
  page,
}) => {
  await loginAsTestUser(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("account");

  await page.locator("#subject").fill("Login problem");

  await page.locator("#message").fill("Short");

  await page.getByRole("button", { name: /send request/i }).click();

  await expect(
    page.getByText(
      "Please describe the problem in at least 10 characters."
    )
  ).toBeVisible();
});


// ---------------------------------------------------------------------------
// SUPPORT-EDGE-06
// ---------------------------------------------------------------------------

test("SUPPORT-EDGE-06: empty message cannot be submitted", async ({
  page,
}) => {
  await loginAsTestUser(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("account");

  await page.locator("#subject").fill("Login problem");

  const sendButton = page.getByRole("button", {
    name: /send request/i,
  });

  await expect(sendButton).toBeVisible();

  await sendButton.click();

  await expect(
    page.getByText(
      "Please describe the problem in at least 10 characters."
    )
  ).toBeVisible();
});


// ---------------------------------------------------------------------------
// SUPPORT-EDGE-07
// ---------------------------------------------------------------------------

test("SUPPORT-EDGE-07: resolved request can be reopened with a message", async ({
  page,
}) => {
  await loginAsTestUser(page);

  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}`,
    async route => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: SUPPORT_REQUEST_ID,
          request_number: "SR-EDGE-001",
          category: "payment",
          subject: "Payment issue",
          status: "resolved",
          priority: "high",
          created_at: "2030-01-01T10:00:00",
          updated_at: "2030-01-01T11:00:00",
          booking_number: null,
          booking_id: null,
          resolved_at: "2030-01-01T11:00:00",
          message_count: 2,
          last_reply_by_admin: true,
          messages: [
            {
              id: "message-1",
              message: "Payment issue was resolved.",
              is_admin: true,
              sender_name: "TicketFlow Support",
              created_at: "2030-01-01T11:00:00",
            },
          ],
        }),
      });
    }
  );

  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}/reopen`,
    async route => {
      const body = route.request().postDataJSON();

      expect(body.message).toBe(
        "The issue is still not fixed."
      );

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: SUPPORT_REQUEST_ID,
          status: "open",
        }),
      });
    }
  );

  await page.goto(`/support/${SUPPORT_REQUEST_ID}`);

  await page
    .getByLabel("Your message")
    .fill("The issue is still not fixed.");

  await page
    .getByRole("button", { name: "Reopen Request" })
    .click();

  await expect(
    page.getByLabel("Your message")
  ).toHaveValue("");
});


// ---------------------------------------------------------------------------
// SUPPORT-EDGE-08
// ---------------------------------------------------------------------------

test("SUPPORT-EDGE-08: closed request does not allow replying", async ({
  page,
}) => {
  await loginAsTestUser(page);

  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}`,
    async route => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: SUPPORT_REQUEST_ID,
          request_number: "SR-EDGE-002",
          category: "account",
          subject: "Account issue",
          status: "closed",
          priority: "normal",
          created_at: "2030-01-01T10:00:00",
          updated_at: "2030-01-01T11:00:00",
          booking_number: null,
          booking_id: null,
          resolved_at: null,
          message_count: 2,
          last_reply_by_admin: true,
          messages: [],
        }),
      });
    }
  );

  await page.goto(`/support/${SUPPORT_REQUEST_ID}`);

  await expect(
    page.getByText(/This request is closed/i)
  ).toBeVisible();

  await expect(
    page.getByText(/raise a new request/i)
  ).toBeVisible();

  await expect(
    page.getByLabel("Your message")
  ).not.toBeVisible();
});