import { test, expect, Page } from "@playwright/test";
import { fakeLogin, FIREBASE_API_KEY, waitForLogin } from "../helpers/fakeLogin";

// #218: "Recommended for you" and "Trending" on the home page, view logging and
// preferences on the profile page. The API is mocked.

const card = (id: string, title: string, extra: Record<string, unknown> = {}) => ({
  event_id: id,
  title,
  event_type: "movie",
  genre: "Thriller",
  language: "Hindi",
  poster_url: null,
  next_show_time: "2030-01-05T13:30:00+00:00",
  city: "Ahmedabad",
  price_from: 180,
  avg_rating: 8.1,
  review_count: 4,
  link: `/events/${id}`,
  ...extra,
});

const TRENDING = [card("t1", "Laugh Riot", { genre: "Comedy", recent_bookings: 12 })];

async function mockRecommendations(page: Page, body: object, seen: string[] = []) {
  await page.route("**/api/recommendations?**", (route) => {
    seen.push(route.request().headers()["authorization"] ? "with-token" : "guest");
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.route("**/api/recommendations", (route) => {
    seen.push(route.request().headers()["authorization"] ? "with-token" : "guest");
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

test("a guest sees trending events only", async ({ page }) => {
  const seen: string[] = [];
  await mockRecommendations(page, {
    personalized: false, recommended: [], trending: TRENDING, ai_reasons: false,
    fallback: "guest", based_on: [],
  }, seen);
  await page.goto("/");

  const trending = page.getByTestId("trending-row");
  await expect(trending).toContainText("Trending now");
  await expect(trending).toContainText("Laugh Riot");
  await expect(trending).toContainText("12 booked in the last 2 weeks");
  await expect(page.getByTestId("recommended-row")).toHaveCount(0);
  await expect(page.getByTestId("preferences-hint")).toHaveCount(0);
  expect(seen[0]).toBe("guest");
});

test.describe("logged in", () => {
  test.skip(!FIREBASE_API_KEY, "Set NEXT_PUBLIC_FIREBASE_API_KEY to the value the frontend was built with");

  test("shows picks with the AI reason", async ({ page }) => {
    await fakeLogin(page, ["customer"]);
    await mockRecommendations(page, {
      personalized: true,
      recommended: [
        card("r1", "Night Chase", {
          match: ["Because you booked Dark Alley"],
          reason: "Another tense crime thriller, like the one you booked.",
        }),
      ],
      trending: TRENDING, ai_reasons: true, fallback: null,
      based_on: ["your bookings", "your preferences"],
    });
    await page.goto("/");
    await waitForLogin(page);

    const row = page.getByTestId("recommended-row");
    await expect(row).toContainText("Recommended for you");
    await expect(row).toContainText("Based on your bookings, your preferences");
    await expect(row.getByTestId("recommendation-reason")).toHaveText(
      "✨ Another tense crime thriller, like the one you booked."
    );
    await expect(row.getByTestId("recommendation-card")).toHaveAttribute("href", "/events/r1");
    await expect(page.getByTestId("trending-row")).toContainText("Laugh Riot");
  });

  test("when the AI is slow, picks show their match label instead", async ({ page }) => {
    await fakeLogin(page, ["customer"]);
    await mockRecommendations(page, {
      personalized: true,
      recommended: [card("r1", "Night Chase", { match: ["You like Thriller"], reason: null })],
      trending: TRENDING, ai_reasons: false, fallback: "ai_timeout", based_on: ["your preferences"],
    });
    await page.goto("/");
    await waitForLogin(page);

    const row = page.getByTestId("recommended-row");
    await expect(row).toContainText("You like Thriller");
    await expect(row.getByTestId("recommendation-reason")).toHaveCount(0);
    await expect(page.getByTestId("trending-row")).toBeVisible();
  });

  test("a new user is pointed to the preferences", async ({ page }) => {
    await fakeLogin(page, ["customer"]);
    await mockRecommendations(page, {
      personalized: false, recommended: [], trending: TRENDING, ai_reasons: false,
      fallback: "no_history", based_on: [],
    });
    await page.goto("/");
    await waitForLogin(page);

    await expect(page.getByTestId("preferences-hint").getByRole("link")).toHaveAttribute(
      "href", "/profile#preferences"
    );
  });

  test("preferences are loaded, edited and saved", async ({ page }) => {
    await fakeLogin(page, ["customer"]);
    await page.route("**/api/profile", (route) => route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ id: "u1", name: "Test User", email: "t@example.com", phone: null,
        birthdate: "2000-01-01", bio: null, avatar_url: null, status: "active",
        created_at: "2025-01-01T00:00:00Z", roles: ["customer"] }),
    }));
    await page.route("**/api/recommendations/preference-options", (route) => route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ genres: ["Comedy", "Thriller"], artists: ["A. R. Rahman"], cities: ["Ahmedabad", "Surat"] }),
    }));
    let saved: any = null;
    await page.route("**/api/recommendations/preferences", (route) => {
      if (route.request().method() === "PUT") {
        saved = route.request().postDataJSON();
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(saved) });
      }
      return route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ genres: ["Thriller"], artists: [], cities: [], updated_at: null }) });
    });

    await page.goto("/profile");
    const form = page.locator("#preferences");
    await expect(form).toContainText("Thriller");
    const save = form.getByRole("button", { name: "Save preferences" });
    await expect(save).toBeDisabled();

    await form.getByRole("button", { name: "+ Comedy" }).click();
    await form.getByLabel(/Favourite artists/).fill("Shreya Ghoshal");
    await form.getByLabel(/Favourite artists/).press("Enter");
    await form.getByRole("button", { name: "+ Surat" }).click();
    await form.getByRole("button", { name: "Remove Thriller" }).click();
    await save.click();

    await expect(page.getByText("Preferences saved")).toBeVisible();
    expect(saved).toEqual({ genres: ["Comedy"], artists: ["Shreya Ghoshal"], cities: ["Surat"] });
    await expect(save).toBeDisabled();
  });

  test("opening an event page records a view", async ({ page }) => {
    await fakeLogin(page, ["customer"]);
    const views: string[] = [];
    await page.route("**/api/recommendations/views/**", (route) => {
      views.push(new URL(route.request().url()).pathname);
      return route.fulfill({ status: 200, contentType: "application/json", body: '{"recorded":true}' });
    });
    await page.route("**/api/browse/events/ev-1", (route) => route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ id: "ev-1", title: "Night Chase", event_type: "movie", shows: [],
        cast_crew: [], artists: [], formats: [], review_count: 0, avg_rating: null }),
    }));
    await page.route("**/api/reviews/**", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" }));
    await page.goto("/events/ev-1");
    await waitForLogin(page);

    await expect.poll(() => views).toEqual(["/api/recommendations/views/ev-1"]);
  });
});
