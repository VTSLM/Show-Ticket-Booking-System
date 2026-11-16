import { test, expect } from "@playwright/test";

test.describe("Browsing - Integration Tests", () => {
  test("BROWSE-INT-01 browse page loads with real backend data", async ({
    page,
  }) => {
    await page.goto("/browse");

    await expect(
      page.getByText("Browse Shows", { exact: true })
    ).toBeVisible();

    await expect(page.getByText("Now showing")).toBeVisible();

    await expect(page.getByText(/\d+ shows?/)).toBeVisible();
  });

  test("BROWSE-INT-02 real shows are displayed from backend", async ({
    page,
  }) => {
    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/api/browse/shows") &&
        response.request().method() === "GET"
    );

    await page.goto("/browse");

    const response = await responsePromise;

    expect(response.status()).toBe(200);

    const data = await response.json();

    expect(Array.isArray(data)).toBe(true);

    if (data.length > 0) {
      const firstShow = data[0];

      expect(firstShow).toHaveProperty("show_id");
      expect(firstShow).toHaveProperty("title");
      expect(firstShow).toHaveProperty("event_type");
      expect(firstShow).toHaveProperty("start_time");
      expect(firstShow).toHaveProperty("venue_name");
      expect(firstShow).toHaveProperty("city");
      expect(firstShow).toHaveProperty("base_price");
      expect(firstShow).toHaveProperty("available_seats");

      await expect(
        page
          .getByRole("link", {
            name: firstShow.title,
          })
          .first()
      ).toBeVisible();
    }
  });

  test("BROWSE-INT-03 real city filter reaches backend", async ({
    page,
  }) => {
    const citiesResponsePromise = page.waitForResponse(
      (response) => new URL(response.url()).pathname === "/api/browse/cities"
    );
    await page.goto("/browse");

    const citySelect = page.getByRole("combobox", {
      name: "Filter by city",
    });

    await expect(citySelect).toBeVisible();

    const citiesResponse = await citiesResponsePromise;
    expect(citiesResponse.ok()).toBe(true);
    const cities: string[] = await citiesResponse.json();
    const availableCity = cities[0];

    test.skip(
      !availableCity,
      "No city available in database"
    );

    const responsePromise = page.waitForResponse(
      (response) => {
        if (
          !response.url().includes("/api/browse/shows") ||
          response.request().method() !== "GET"
        ) {
          return false;
        }

        const url = new URL(response.url());

        return url.searchParams.get("city") === availableCity;
      }
    );

    await citySelect.selectOption(availableCity!);

    const response = await responsePromise;

    expect(response.status()).toBe(200);

    const url = new URL(response.url());

    expect(url.searchParams.get("city")).toBe(
      availableCity
    );
  });

  test("BROWSE-INT-04 real search reaches backend", async ({
    page,
  }) => {
    await page.goto("/browse");

    const searchInput = page.getByRole("textbox", {
      name: "Search movies, venues, genres, or cities",
    });

    await expect(searchInput).toBeVisible();

    const searchTerm = "spider";

    const responsePromise = page.waitForResponse(
      (response) => {
        if (
          !response.url().includes("/api/browse/shows") ||
          response.request().method() !== "GET"
        ) {
          return false;
        }

        const url = new URL(response.url());

        return url.searchParams.get("search") === searchTerm;
      }
    );

    await searchInput.fill(searchTerm);

    await page.getByRole("button", {
      name: "Search",
      exact: true,
    }).click();

    const response = await responsePromise;

    expect(response.status()).toBe(200);

    const url = new URL(response.url());

    expect(url.searchParams.get("search")).toBe(
      searchTerm
    );
  });

  test("BROWSE-INT-05 real event type filter reaches backend", async ({
    page,
  }) => {
    await page.goto("/browse");

    const movies = page.getByRole("button", { name: /Movies/ });
    await expect(movies).toBeVisible();
    const expectedEventType = "movie";

    const responsePromise = page.waitForResponse(
      (response) => {
        if (
          !response.url().includes("/api/browse/shows") ||
          response.request().method() !== "GET"
        ) {
          return false;
        }

        const url = new URL(response.url());

        return (
          url.searchParams.get("event_type")?.toLowerCase() ===
          expectedEventType
        );
      }
    );

    await movies.click();

    const response = await responsePromise;

    expect(response.status()).toBe(200);

    const url = new URL(response.url());

    expect(
      url.searchParams.get("event_type")?.toLowerCase()
    ).toBe(expectedEventType);
  });

  test("BROWSE-INT-06 real show links to event details", async ({
    page,
  }) => {
    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/api/browse/shows") &&
        response.request().method() === "GET"
    );

    await page.goto("/browse");

    const response = await responsePromise;

    expect(response.status()).toBe(200);

    const data = await response.json();

    test.skip(
      data.length === 0,
      "No shows available in database"
    );

    const firstShow = data[0];

    const showLink = page
      .getByRole("link", {
        name: firstShow.title,
      })
      .first();

    await expect(showLink).toBeVisible();

    await expect(showLink).toHaveAttribute(
      "href",
      `/events/${firstShow.event_id}`
    );
  });

  test("BROWSE-INT-07 cities endpoint returns real database cities", async ({
    page,
  }) => {
    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().includes("/api/browse/cities") &&
        response.request().method() === "GET"
    );

    await page.goto("/browse");

    const response = await responsePromise;

    expect(response.status()).toBe(200);

    const cities = await response.json();

    expect(Array.isArray(cities)).toBe(true);

    const citySelect = page.getByRole("combobox", {
      name: "Filter by city",
    });

    await expect.poll(() => citySelect.locator("option").evaluateAll(
      (options) => options.map((option) => (option as HTMLOptionElement).value).filter(Boolean)
    )).toEqual(cities);
  });
});
