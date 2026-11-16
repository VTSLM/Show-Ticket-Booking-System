import { test, expect, Page } from "@playwright/test";

const SUPPORT_REQUEST_ID = "support-123";
const BOOKING_ID = "booking-123";

const OPEN_REQUEST = {
  id: SUPPORT_REQUEST_ID,
  request_number: "SR-20261114-ABC123",
  category: "booking",
  subject: "Booking problem",
  status: "open",
  priority: "normal",
  created_at: "2026-11-14T08:00:00Z",
  updated_at: "2026-11-14T08:00:00Z",
  booking_number: "BK-12345",
  message_count: 1,
  last_reply_by_admin: false,
  booking_id: BOOKING_ID,
  resolved_at: null,
  user_name: "Test User",
  user_email: "test@example.com",
  messages: [
    {
      id: "message-1",
      message: "I cannot access my booking.",
      is_admin: false,
      sender_name: "Test User",
      created_at: "2026-11-14T08:00:00Z",
    },
  ],
};

const RESOLVED_REQUEST = {
  ...OPEN_REQUEST,
  status: "resolved",
  resolved_at: "2026-11-14T10:00:00Z",
  messages: [
    ...OPEN_REQUEST.messages,
    {
      id: "message-2",
      message: "Your issue has been resolved.",
      is_admin: true,
      sender_name: "TicketFlow Support",
      created_at: "2026-11-14T10:00:00Z",
    },
  ],
};

const CLOSED_REQUEST = {
  ...OPEN_REQUEST,
  status: "closed",
};

const BOOKINGS = [
  {
    id: BOOKING_ID,
    booking_number: "BK-12345",
    show_title: "Test Movie",
    show_date: "2026-11-20",
  },
];

async function loginAsTestUser(page: Page) {
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

  await expect(page).toHaveURL(/\/browse/);
}

async function mockSupportApis(page: Page) {
  // /support/new uses bookingsApi.list(),
  // which calls GET /api/bookings.
  await page.route("**/api/bookings", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(BOOKINGS),
      });
      return;
    }

    await route.continue();
  });

  await page.route("**/api/support/requests", async (route) => {
    const request = route.request();
    const method = request.method();

    // Create support request
    if (method === "POST") {
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: SUPPORT_REQUEST_ID,
          request_number: OPEN_REQUEST.request_number,
        }),
      });
      return;
    }

    // Get support requests
    if (method === "GET") {
      // The customer support page fetches the list once
      // and filters the returned array locally.
      const response = [
        OPEN_REQUEST,
        RESOLVED_REQUEST,
        CLOSED_REQUEST,
      ];

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(response),
      });
      return;
    }

    await route.continue();
  });

  // Get individual support request
  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}`,
    async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(OPEN_REQUEST),
      });
    }
  );

  // Send reply
  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}/messages`,
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }

      const body = route.request().postDataJSON();

      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "message-reply-1",
          message: body.message,
          is_admin: false,
          sender_name: "Test User",
          created_at: "2026-11-14T11:00:00Z",
        }),
      });
    }
  );

  // Reopen request
  await page.route(
    `**/api/support/requests/${SUPPORT_REQUEST_ID}/reopen`,
    async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }

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
}


/* ============================================================
   SUPPORT-INT-01
   Customer creates a support request
   ============================================================ */

test(
  "SUPPORT-INT-01: customer can create a support request",
  async ({ page }) => {
    await loginAsTestUser(page);
    await mockSupportApis(page);

    await page.goto("/support");

    await expect(
      page.getByRole("heading", { name: "My Support Requests" })
    ).toBeVisible();

    await page.getByRole("link", {
      name: /\+ New Request/i,
    }).click();

    await expect(
      page.getByRole("heading", { name: "Contact Support" })
    ).toBeVisible();

    await page.locator("#category").selectOption("booking");

    await page.locator("#booking").selectOption(BOOKING_ID);

    await page.locator("#subject").fill("Booking problem");

    await page
      .locator("#message")
      .fill("I cannot access my booking.");

    await page.getByRole("button", {
      name: /send request/i,
    }).click();

    await expect(page).toHaveURL(
      new RegExp(`/support/${SUPPORT_REQUEST_ID}`)
    );
  }
);


/* ============================================================
   SUPPORT-INT-02
   Customer opens a request and sends a reply
   ============================================================ */

test(
  "SUPPORT-INT-02: customer can view a request and send a reply",
  async ({ page }) => {
    await loginAsTestUser(page);
    await mockSupportApis(page);

    await page.goto(`/support/${SUPPORT_REQUEST_ID}`);

    await expect(
      page.getByRole("heading", { name: "Booking problem" })
    ).toBeVisible();

    await expect(
      page.getByText("I cannot access my booking.", {
        exact: true,
      })
    ).toBeVisible();

    await page
      .getByLabel("Your message")
      .fill("I have additional information about the booking.");

    await page.getByRole("button", {
      name: /^send$/i,
    }).click();

    await expect(
      page.getByText(
        "I have additional information about the booking.",
        { exact: true }
      )
    ).toBeVisible();
  }
);


/* ============================================================
   SUPPORT-INT-03
   Resolved request can be reopened
   ============================================================ */

test(
  "SUPPORT-INT-03: resolved request can be reopened with a message",
  async ({ page }) => {
    await loginAsTestUser(page);

    await page.route(
      `**/api/support/requests/${SUPPORT_REQUEST_ID}`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(RESOLVED_REQUEST),
        });
      }
    );

    await page.route(
      `**/api/support/requests/${SUPPORT_REQUEST_ID}/reopen`,
      async (route) => {
        const body = route.request().postDataJSON();

        expect(body.message).toBe(
          "The issue has occurred again."
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

    await expect(
      page.getByRole("button", {
        name: /reopen request/i,
      })
    ).toBeVisible();

    await page
      .getByLabel("Your message")
      .fill("The issue has occurred again.");

    await page.getByRole("button", {
      name: /reopen request/i,
    }).click();

    await expect(
      page.getByText(
        "Request reopened. Our team will take another look."
      )
    ).toBeVisible();
  }
);


/* ============================================================
   SUPPORT-INT-04
   Customer filters requests by status
   ============================================================ */

test(
  "SUPPORT-INT-04: customer can filter support requests by status",
  async ({ page }) => {
    await loginAsTestUser(page);

    await page.route("**/api/support/requests", async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }

      const response = [
        {
          ...OPEN_REQUEST,
          id: "open-request",
          request_number: "SR-OPEN-001",
          subject: "Open booking problem",
          status: "open",
        },
        {
          ...RESOLVED_REQUEST,
          id: "resolved-request",
          request_number: "SR-RESOLVED-001",
          subject: "Resolved payment issue",
          status: "resolved",
        },
        {
          ...CLOSED_REQUEST,
          id: "closed-request",
          request_number: "SR-CLOSED-001",
          subject: "Closed account issue",
          status: "closed",
        },
      ];

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(response),
      });
    });

    await page.goto("/support");

    // All requests should initially be visible.
    await expect(
      page.getByText("Open booking problem", { exact: true })
    ).toBeVisible();

    await expect(
      page.getByText("Resolved payment issue", { exact: true })
    ).toBeVisible();

    await expect(
      page.getByText("Closed account issue", { exact: true })
    ).toBeVisible();

    // Filter to resolved requests.
    await page.getByRole("button", {
      name: /resolved/i,
    }).click();

    // Only the resolved request should remain visible.
    await expect(
      page.getByText("Resolved payment issue", { exact: true })
    ).toBeVisible();

    await expect(
      page.getByText("Open booking problem", { exact: true })
    ).not.toBeVisible();

    await expect(
      page.getByText("Closed account issue", { exact: true })
    ).not.toBeVisible();
  }
);


/* ============================================================
   SUPPORT-INT-05
   Closed request cannot be replied to
   ============================================================ */

test(
  "SUPPORT-INT-05: closed request does not allow customer reply",
  async ({ page }) => {
    await loginAsTestUser(page);

    await page.route(
      `**/api/support/requests/${SUPPORT_REQUEST_ID}`,
      async (route) => {
        if (route.request().method() === "GET") {
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              ...CLOSED_REQUEST,
              status: "closed",
            }),
          });
          return;
        }

        await route.continue();
      }
    );

    await page.goto(`/support/${SUPPORT_REQUEST_ID}`);

    await expect(
      page.getByText(/This request is closed/)
    ).toBeVisible();

    await expect(
      page.getByLabel("Your message")
    ).not.toBeVisible();

    await expect(
      page.getByRole("button", {
        name: /^send$/i,
      })
    ).not.toBeVisible();
  }
);