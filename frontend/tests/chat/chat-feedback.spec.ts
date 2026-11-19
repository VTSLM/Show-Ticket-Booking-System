import { test, expect } from "@playwright/test";

test.describe("Chat Feedback", () => {
  test("CHAT-FEEDBACK-01: user can submit positive feedback for an assistant reply", async ({
    page,
  }) => {
    const replyId = "123e4567-e89b-12d3-a456-426614174000";

    // Mock the streaming chat response.
    await page.route("**/api/chat/stream", async (route) => {
      const body = [
        `data: ${JSON.stringify({
          type: "delta",
          text: "Here are some shows you may like.",
        })}\n\n`,
        `data: ${JSON.stringify({
          type: "done",
          reply_id: replyId,
        })}\n\n`,
      ].join("");

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body,
      });
    });

    let feedbackRequest: {
      reply_id?: string;
      rating?: number;
    } = {};

    // Intercept feedback submission.
    await page.route("**/api/chat/feedback", async (route) => {
      feedbackRequest = route.request().postDataJSON();

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    });

    // Open the chatbot.
    await page.getByRole("button", { name: /chat|ask ticketflow/i }).click();

    // Enter a message.
    const input = page.getByPlaceholder(/ask ticketflow|type your message|message/i);

    await input.fill("What shows are available?");
    await input.press("Enter");

    // Assistant reply should appear.
    await expect(
      page.getByText("Here are some shows you may like.")
    ).toBeVisible();

    // Feedback controls should appear.
    await expect(
      page.getByRole("button", { name: "Helpful" })
    ).toBeVisible();

    await expect(
      page.getByRole("button", { name: "Not helpful" })
    ).toBeVisible();

    // Submit positive feedback.
    await page.getByRole("button", { name: "Helpful" }).click();

    // Verify the request sent the correct reply ID and rating.
    expect(feedbackRequest.reply_id).toBe(replyId);
    expect(feedbackRequest.rating).toBe(1);

    // Verify the UI changes after submission.
    await expect(
      page.getByText(/Thanks for your feedback! 👍/)
    ).toBeVisible();

    // Buttons should no longer be available for another submission.
    await expect(
      page.getByRole("button", { name: "Helpful" })
    ).not.toBeVisible();

    await expect(
      page.getByRole("button", { name: "Not helpful" })
    ).not.toBeVisible();
  });

  test("CHAT-FEEDBACK-02: user can submit negative feedback", async ({
    page,
  }) => {
    const replyId = "123e4567-e89b-12d3-a456-426614174001";

    await page.route("**/api/chat/stream", async (route) => {
      const body = [
        `data: ${JSON.stringify({
          type: "delta",
          text: "I couldn't find a suitable show.",
        })}\n\n`,
        `data: ${JSON.stringify({
          type: "done",
          reply_id: replyId,
        })}\n\n`,
      ].join("");

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body,
      });
    });

    let feedbackRequest: {
      reply_id?: string;
      rating?: number;
    } = {};

    await page.route("**/api/chat/feedback", async (route) => {
      feedbackRequest = route.request().postDataJSON();

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true }),
      });
    });

    await page.getByRole("button", { name: /chat|ask ticketflow/i }).click();

    const input = page.getByPlaceholder(/ask ticketflow|type your message|message/i);

    await input.fill("Find me a show");
    await input.press("Enter");

    await expect(
      page.getByText("I couldn't find a suitable show.")
    ).toBeVisible();

    await page.getByRole("button", { name: "Not helpful" }).click();

    expect(feedbackRequest.reply_id).toBe(replyId);
    expect(feedbackRequest.rating).toBe(-1);

    await expect(
      page.getByText(/Thanks for your feedback! 👎/)
    ).toBeVisible();
  });
});