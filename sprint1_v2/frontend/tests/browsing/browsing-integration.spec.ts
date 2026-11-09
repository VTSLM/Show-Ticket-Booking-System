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

    await expect(page.getByText(/\d+ shows/)).toBeVisible();
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
            name: new RegExp(firstShow.title, "i"),
          })
          .first()
      ).toBeVisible();
    }
  });

  test("BROWSE-INT-03 real city filter reaches backend", async ({
    page,
  }) => {
    await page.goto("/browse");

    const citySelect = page.getByRole("combobox", {
      name: "Filter by city",
    });

    await expect(citySelect).toBeVisible();

    const options = await citySelect.locator("option").allTextContents();

    const availableCity = options.find(
      (city) =>
        city.trim() !== "" &&
        city.trim() !== "All cities"
    );

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

    await citySelect.selectOption({
      label: availableCity!,
    });

    await page.getByRole("button", {
      name: "Search",
    }).click();

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
      name: "Search shows or venues",
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

    const eventTypeSelect = page.getByRole("combobox", {
      name: "Filter by show type",
    });

    await expect(eventTypeSelect).toBeVisible();

    const options = await eventTypeSelect
      .locator("option")
      .allTextContents();

    const eventType = options.find(
      (value) =>
        value.trim() !== "" &&
        value.trim() !== "All types"
    );

    test.skip(
      !eventType,
      "No event type available in database"
    );

    const expectedEventType = eventType!.toLowerCase();

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

    await eventTypeSelect.selectOption({
      label: eventType!,
    });

    await page.getByRole("button", {
      name: "Search",
    }).click();

    const response = await responsePromise;

    expect(response.status()).toBe(200);

    const url = new URL(response.url());

    expect(
      url.searchParams.get("event_type")?.toLowerCase()
    ).toBe(expectedEventType);
  });

  test("BROWSE-INT-06 real show links to seat selection", async ({
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
        name: new RegExp(firstShow.title, "i"),
      })
      .first();

    await expect(showLink).toBeVisible();

    await expect(showLink).toHaveAttribute(
      "href",
      `/shows/${firstShow.show_id}/seats`
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

    const options = await citySelect
      .locator("option")
      .allTextContents();

    for (const city of cities) {
      expect(options).toContain(city);
    }
  });
});