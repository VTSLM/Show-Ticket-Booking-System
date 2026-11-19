import { test, expect } from "@playwright/test";

const chatEnabled =
  process.env.NEXT_PUBLIC_CHAT_ENABLED !== "false";


test.describe("Chatbot feature flag", () => {
  test("CHAT-UI-01: chatbot visibility follows CHAT_ENABLED", async ({
    page,
  }) => {
    await page.goto("/");

    const chatButton = page.getByRole(
      "button",
      {
        name: "Open the TicketFlow assistant",
      },
    );

    if (chatEnabled) {
      await expect(chatButton).toBeVisible();
    } else {
      await expect(chatButton).not.toBeVisible();
    }
  });
});