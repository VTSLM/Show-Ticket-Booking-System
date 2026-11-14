import { test, expect } from "@playwright/test";

const SUPPORT_REQUEST_ID = "support-123";
const BOOKING_ID = "booking-123";

const TEST_REQUEST = {
  id: SUPPORT_REQUEST_ID,
  request_number: "SUP-2026-0001",
  category: "booking",
  subject: "Booking problem",
  status: "open",
  priority: "normal",
  created_at: "2026-11-10T10:00:00Z",
  updated_at: "2026-11-10T10:00:00Z",
  booking_number: "BK-2026-0001",
  message_count: 1,
  last_reply_by_admin: false,
  user_name: "Test User",
};

const TEST_DETAIL = {
  ...TEST_REQUEST,
  booking_id: BOOKING_ID,
  resolved_at: null,
  user_email: "test@example.com",
  messages: [
    {
      id: "message-1",
      message: "I cannot access my booking.",
      is_admin: false,
      sender_name: "Test User",
      created_at: "2026-11-10T10:00:00Z",
    },
  ],
};

const RESOLVED_REQUEST = {
  ...TEST_DETAIL,
  status: "resolved",
  resolved_at: "2026-11-11T10:00:00Z",
  messages: [
    {
      id: "message-1",
      message: "I cannot access my booking.",
      is_admin: false,
      sender_name: "Test User",
      created_at: "2026-11-10T10:00:00Z",
    },
    {
      id: "message-2",
      message: "The issue has been resolved.",
      is_admin: true,
      sender_name: "TicketFlow Support",
      created_at: "2026-11-11T10:00:00Z",
    },
  ],
};

const CLOSED_REQUEST = {
  ...TEST_DETAIL,
  status: "closed",
  messages: [
    {
      id: "message-1",
      message: "I cannot access my booking.",
      is_admin: false,
      sender_name: "Test User",
      created_at: "2026-11-10T10:00:00Z",
    },
    {
      id: "message-2",
      message: "This issue has been closed.",
      is_admin: true,
      sender_name: "TicketFlow Support",
      created_at: "2026-11-11T10:00:00Z",
    },
  ],
};

const BOOKINGS = [
  {
    id: BOOKING_ID,
    event_title: "Spider Man",
    start_time: "2026-11-20T18:30:00Z",
    total_amount: "700",
    status: "confirmed",
    booking_number: "BK-2026-0001",
  },
];

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

  // Use the actual password input.
  // getByLabel(/password/i) can also match the Show password button.
  await page.locator("#password").fill(password);

  await page.getByRole("button", {
    name: /log\s*in|sign\s*in/i,
  }).click();

  await expect(page).toHaveURL(/\/browse/, {
    timeout: 15_000,
  });

  await page.waitForTimeout(1500);
}

async function mockSupportApis(page: any) {
  // -----------------------------------------------------------------------
  // Bookings
  // -----------------------------------------------------------------------
  await page.route("**/api/bookings**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(BOOKINGS),
    });
  });

  // -----------------------------------------------------------------------
  // Support request list + create request
  // IMPORTANT:
  // GET and POST are handled by the SAME route so that the GET request
  // cannot accidentally fall through to the real backend.
  // -----------------------------------------------------------------------
  await page.route("**/api/support/requests", async (route) => {
    const method = route.request().method();

    // -----------------------------
    // CREATE SUPPORT REQUEST
    // -----------------------------
    if (method === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: SUPPORT_REQUEST_ID,
          request_number: "SUP-2026-0001",
        }),
      });

      return;
    }

    // -----------------------------
    // LIST SUPPORT REQUESTS
    // -----------------------------
    if (method === "GET") {
      const url = new URL(route.request().url());
      const status = url.searchParams.get("status");

      if (status === "resolved") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "support-resolved",
              request_number: "SUP-2026-0002",
              category: "payment",
              subject: "Payment issue resolved",
              status: "resolved",
              priority: "normal",
              created_at: "2026-11-09T10:00:00Z",
              updated_at: "2026-11-11T10:00:00Z",
              booking_number: "BK-2026-0002",
              message_count: 2,
              last_reply_by_admin: true,
              user_name: "Test User",
            },
          ]),
        });

        return;
      }

      if (status === "closed") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "support-closed",
              request_number: "SUP-2026-0003",
              category: "account",
              subject: "Closed account issue",
              status: "closed",
              priority: "normal",
              created_at: "2026-11-09T10:00:00Z",
              updated_at: "2026-11-11T10:00:00Z",
              booking_number: null,
              message_count: 2,
              last_reply_by_admin: true,
              user_name: "Test User",
            },
          ]),
        });

        return;
      }

      // Default: return normal support requests
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          TEST_REQUEST,
          {
            id: "support-resolved",
            request_number: "SUP-2026-0002",
            category: "payment",
            subject: "Payment issue resolved",
            status: "resolved",
            priority: "normal",
            created_at: "2026-11-09T10:00:00Z",
            updated_at: "2026-11-11T10:00:00Z",
            booking_number: "BK-2026-0002",
            message_count: 2,
            last_reply_by_admin: true,
            user_name: "Test User",
          },
        ]),
      });

      return;
    }

    await route.continue();
  });

  // -----------------------------------------------------------------------
  // Request details
  // -----------------------------------------------------------------------
  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}`,
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(TEST_DETAIL),
      });
    }
  );

  await page.route(
    "**/api/support/requests/support-resolved",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(RESOLVED_REQUEST),
      });
    }
  );

  await page.route(
    "**/api/support/requests/support-closed",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(CLOSED_REQUEST),
      });
    }
  );

  // -----------------------------------------------------------------------
  // Customer reply
  // -----------------------------------------------------------------------
  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}/messages`,
    async (route) => {
      const body = route.request().postDataJSON();

      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "message-new",
          message:
            body?.message ??
            "I have additional information about the booking.",
          is_admin: false,
          sender_name: "Test User",
          created_at: "2026-11-13T10:00:00Z",
        }),
      });
    }
  );

  // -----------------------------------------------------------------------
  // Reopen request
  // -----------------------------------------------------------------------
  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}/reopen`,
    async (route) => {
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

  await page.route(
    "**/api/support/requests/support-resolved/reopen",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "support-resolved",
          status: "open",
        }),
      });
    }
  );
}


/* ========================================================================= */
/* SUPPORT UI TESTS                                                          */
/* ========================================================================= */

test("SUPPORT-UI-01: support requests page loads", async ({ page }) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support");

  await expect(
    page.getByRole("heading", { name: "My Support Requests" })
  ).toBeVisible();

  await expect(
    page.getByText("Booking problem", { exact: true })
  ).toBeVisible();
});


test("SUPPORT-UI-02: new request button opens support form", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support");

  await page.getByRole("link", { name: /\+ New Request/i }).click();

  await expect(page).toHaveURL(/\/support\/new/);

  await expect(
    page.getByRole("heading", { name: "Contact Support" })
  ).toBeVisible();
});


test("SUPPORT-UI-03: all support categories are available", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/new");

  const category = page.locator("#category");

  await expect(category.locator("option")).toHaveCount(5);

  await expect(
    category.locator("option", { hasText: "Payment issue" })
  ).toBeAttached();

  await expect(
    category.locator("option", { hasText: "Booking issue" })
  ).toBeAttached();

  await expect(
    category.locator("option", { hasText: "Refund request" })
  ).toBeAttached();

  await expect(
    category.locator("option", { hasText: "Account / login" })
  ).toBeAttached();

  await expect(
    category.locator("option", { hasText: "Something else" })
  ).toBeAttached();
});


test("SUPPORT-UI-04: booking is required for booking category", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("booking");

  await page.locator("#subject").fill("Booking problem");

  // Actual new-request textarea is #message.
  await page.locator("#message").fill(
    "I cannot access my booking."
  );

  await page.getByRole("button", { name: /send request/i }).click();

  await expect(
    page.getByText("Please select the booking this is about.")
  ).toBeVisible();
});


test("SUPPORT-UI-05: booking is required for refund category", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("refund");

  await page.locator("#subject").fill("Refund problem");

  await page.locator("#message").fill(
    "I have not received my refund."
  );

  await page.getByRole("button", { name: /send request/i }).click();

  await expect(
    page.getByText("Please select the booking this is about.")
  ).toBeVisible();
});


test("SUPPORT-UI-06: booking is optional for account category", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("account");

  await expect(
    page.getByText("(optional)", { exact: true })
  ).toBeVisible();

  await page.locator("#subject").fill("Login problem");

  await page.locator("#message").fill(
    "I cannot log into my account."
  );

  await page.getByRole("button", { name: /send request/i }).click();

  await expect(page).toHaveURL(/\/support\/support-123/);
});


test("SUPPORT-UI-07: subject validation is displayed", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("account");

  await page.locator("#subject").fill("Test");

  await page.locator("#message").fill(
    "This is a valid support message."
  );

  await page.getByRole("button", { name: /send request/i }).click();

  await expect(
    page.getByText("Subject must be at least 5 characters.")
  ).toBeVisible();
});


test("SUPPORT-UI-08: message validation is displayed", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("account");

  await page.locator("#subject").fill("Valid subject");

  await page.locator("#message").fill("Help");

  await page.getByRole("button", { name: /send request/i }).click();

  await expect(
    page.getByText(
      "Please describe the problem in at least 10 characters."
    )
  ).toBeVisible();
});


test("SUPPORT-UI-09: booking can be selected for booking request", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("booking");

  const booking = page.locator("#booking");

  await expect(
    booking.locator(`option[value="${BOOKING_ID}"]`)
  ).toBeAttached();

  await booking.selectOption(BOOKING_ID);

  await expect(booking).toHaveValue(BOOKING_ID);
});


test("SUPPORT-UI-10: support request can be submitted", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/new");

  await page.locator("#category").selectOption("booking");

  await page.locator("#booking").selectOption(BOOKING_ID);

  await page.locator("#subject").fill("Booking problem");

  await page.locator("#message").fill(
    "I cannot access my booking."
  );

  await page.getByRole("button", { name: /send request/i }).click();

  await expect(page).toHaveURL(/\/support\/support-123/);
});


test("SUPPORT-UI-11: support request details are displayed", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto(`/support/${SUPPORT_REQUEST_ID}`);

  await expect(
    page.getByText("SUP-2026-0001", { exact: true })
  ).toBeVisible();

  await expect(
    page.getByRole("heading", { name: "Booking problem" })
  ).toBeVisible();

  // Exact match avoids the "Open" vs "Opened" strict-mode issue.
  await expect(
    page.getByText("Open", { exact: true })
  ).toBeVisible();

  await expect(
    page.getByText("I cannot access my booking.", { exact: true })
  ).toBeVisible();
});


test("SUPPORT-UI-12: customer can send a reply", async ({ page }) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto(`/support/${SUPPORT_REQUEST_ID}`);

  // Detail-page reply textarea really is aria-label="Your message".
  const reply = page.getByLabel("Your message");

  await expect(reply).toBeVisible();

  await reply.fill(
    "I have additional information about the booking."
  );

  await page.getByRole("button", { name: /^Send$/i }).click();

  await expect(
    page.getByText(
      "I have additional information about the booking.",
      { exact: true }
    )
  ).toBeVisible();
});


test("SUPPORT-UI-13: resolved request displays reopen option", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/support-resolved");

  await expect(
    page.getByRole("button", { name: /reopen request/i })
  ).toBeVisible();
});


test("SUPPORT-UI-14: closed request does not show reply form", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support/support-closed");

  await expect(
    page.getByText("This request is closed.", { exact: false })
  ).toBeVisible();

  await expect(
    page.getByLabel("Your message")
  ).not.toBeVisible();

  await expect(
    page.getByRole("button", { name: /send/i })
  ).not.toBeVisible();
});


test("SUPPORT-UI-15: support requests can be filtered by status", async ({
  page,
}) => {
  await loginAsTestUser(page);
  await mockSupportApis(page);

  await page.goto("/support");

  await expect(
    page.getByText("Booking problem", { exact: true })
  ).toBeVisible();

  await page.getByRole("button", {
    name: /Resolved \(1\)/i,
  }).click();

  await expect(
    page.getByText("Payment issue resolved", { exact: true })
  ).toBeVisible();

  await expect(
    page.getByText("Booking problem", { exact: true })
  ).not.toBeVisible();
});