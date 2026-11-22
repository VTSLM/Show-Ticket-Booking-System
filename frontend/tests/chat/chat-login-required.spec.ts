import { test, expect } from "@playwright/test";
import { fakeLogin, FIREBASE_API_KEY, waitForLogin } from "../helpers/fakeLogin";

// #204: only logged-in users can use the assistant. The API is mocked.

const CHAT_ENABLED = process.env.NEXT_PUBLIC_CHAT_ENABLED !== "false";
test.skip(!CHAT_ENABLED, "The chatbot is switched off in this build");

const openButton = (page: import("@playwright/test").Page) =>
  page.getByRole("button", { name: "Open the TicketFlow assistant" });

test("a guest sees a log-in notification instead of the chat", async ({ page }) => {
  let chatCalls = 0;
  await page.route("**/api/chat/**", (route) => { chatCalls += 1; return route.abort(); });
  await page.route("**/api/browse/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.goto("/browse?event_type=movie");

  await openButton(page).click();

  const toast = page.getByTestId("chat-login-toast");
  await expect(toast).toContainText("Log in to use the TicketFlow AI Assistant");
  await expect(page.getByRole("dialog", { name: "TicketFlow assistant" })).toHaveCount(0);
  expect(chatCalls).toBe(0);

  // The Log in link brings the guest back to the same page afterwards
  await expect(toast.getByRole("link", { name: "Log in" })).toHaveAttribute(
    "href", `/auth/login?redirect=${encodeURIComponent("/browse?event_type=movie")}`
  );

  // Clicking again does not stack a second notification
  await openButton(page).click();
  await expect(page.getByTestId("chat-login-toast")).toHaveCount(1);
});

test("a logged-in user can open the chat", async ({ page }) => {
  test.skip(!FIREBASE_API_KEY, "Set NEXT_PUBLIC_FIREBASE_API_KEY to the value the frontend was built with");
  await fakeLogin(page, ["customer"]);
  await page.route("**/api/browse/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
  await page.goto("/browse");
  await waitForLogin(page);

  await openButton(page).click();

  await expect(page.getByRole("dialog", { name: "TicketFlow assistant" })).toBeVisible();
  await expect(page.getByTestId("chat-login-toast")).toHaveCount(0);
});
