import { test, expect, Page } from "@playwright/test";

// Stadium / arena seat maps (#198). The API is mocked, so no backend is needed.
const SHOW = "99999999-9999-9999-9999-999999999999";
const ROWS = ["A", "B", "C", "D", "E", "F"];
const SEATS = ROWS.flatMap((row, r) =>
  Array.from({ length: 20 }, (_, i) => ({
    show_seat_id: `${row}${i + 1}`, row_label: row, seat_number: i + 1,
    seat_type: r < 2 ? "premium" : "standard", status: i === 3 ? "booked" : "available",
    price: r < 2 ? 2999 : 1499, section_name: r < 2 ? "Grandstand Premium" : "Grandstand",
    x_pos: i * 40, y_pos: r * 40, // stored grid positions, which an arena must not use
  }))
);
const ZONES = [
  { id: "z-ga", name: "Gold Standing", zone_type: "general", total_capacity: 1200, booked_count: 0, locked_count: 0, available_capacity: 1200, price: 2499, display_order: 2 },
  { id: "z-pit", name: "VIP Fan Pit", zone_type: "fan_pit", total_capacity: 400, booked_count: 0, locked_count: 0, available_capacity: 400, price: 4999, display_order: 1 },
];

async function open(page: Page, stagePosition: string, layoutType = "concert") {
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.route("**/api/**", (route) => {
    const url = route.request().url();
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (/\/api\/seats\/[^/?]+\/map/.test(url)) {
      return json({ layout_type: layoutType, stage_position: stagePosition, zones: ZONES, seats: SEATS, terms_and_conditions: "", terms_hash: "x" });
    }
    if (/\/api\/browse\/shows\//.test(url)) return json({ id: SHOW, show_id: SHOW, title: "Neon Skyline Tour", start_time: "2030-01-10T14:00:00Z" });
    return json([]);
  });
  await page.goto(`/shows/${SHOW}/seats`);
  await expect(page.locator('[data-seat="A1"]')).toBeVisible();
}

async function seatBox(page: Page, id: string) {
  const r = await page.locator(`[data-seat="${id}"]`).boundingBox();
  return r ? { x: r.x + r.width / 2, y: r.y + r.height / 2 } : null;
}

for (const position of ["front", "center"]) {
  test(`${position} stage: seats wrap round the stage in curved tiers`, async ({ page }) => {
    await open(page, position);
    await expect(page.getByTestId("arena-tiers")).toBeVisible();
    const a1 = await seatBox(page, "A1");
    const a10 = await seatBox(page, "A10");
    const a20 = await seatBox(page, "A20");
    expect(a1 && a10 && a20).toBeTruthy();
    // A row is an arc, not a straight line: its middle seat is well off the line through its ends
    const mid = { x: (a1!.x + a20!.x) / 2, y: (a1!.y + a20!.y) / 2 };
    expect(Math.hypot(a10!.x - mid.x, a10!.y - mid.y)).toBeGreaterThan(80);

    // Fan Pit and standing floor are drawn as rings, Fan Pit closest to the stage
    const zones = page.getByTestId("arena-zone");
    await expect(zones).toHaveCount(2);
    await expect(zones.first()).toContainText("VIP FAN PIT");

    // Whole layout fits in the view after auto-fit
    const view = await page.locator("div.h-\\[550px\\]").boundingBox();
    const tiers = await page.getByTestId("arena-tiers").boundingBox();
    expect(tiers!.x).toBeGreaterThanOrEqual(view!.x - 1);
    expect(tiers!.x + tiers!.width).toBeLessThanOrEqual(view!.x + view!.width + 1);
    expect(tiers!.y + tiers!.height).toBeLessThanOrEqual(view!.y + view!.height + 1);

    await page.screenshot({ path: `test-results/stadium-${position}.png` });
  });
}

test("seats and standing zones can still be clicked in an arena", async ({ page }) => {
  await open(page, "front");
  await page.locator('[data-seat="C5"]').click();
  await expect(page.getByText(/Selected:\s*1\s*seat/)).toBeVisible();
  // A guest picking a pass is asked to log in, which shows the click reached the zone
  await page.getByTestId("arena-zone").first().getByText("VIP FAN PIT").click();
  await expect(page).toHaveURL(/\/auth\/login/);
});

test("cinema layouts keep their straight rows", async ({ page }) => {
  await open(page, "front", "cinema");
  await expect(page.getByTestId("arena-tiers")).toHaveCount(0);
});
