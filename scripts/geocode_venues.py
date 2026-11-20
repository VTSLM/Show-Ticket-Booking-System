#!/usr/bin/env python3
"""
Fill venues.latitude / venues.longitude from each venue's address (OpenStreetMap Nominatim).

Venues without coordinates are placed at the centre of their city on the browse page.
Run this once after applying migration 0025, and again after adding venues:

    cd backend
    python ../scripts/geocode_venues.py --dry-run   # only print what it would do
    python ../scripts/geocode_venues.py             # write the coordinates

Uses DATABASE_URL from backend/.env. Nominatim allows 1 request per second, so this
waits between lookups. Always check the printed results; a wrong guess is better fixed
by editing the venue's latitude/longitude directly.
"""
import argparse
import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import get_pool  # noqa: E402

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TicketFlow-venue-geocoder/1.0 (student project)"


def queries_for(venue: dict) -> list[str]:
    """Most specific search first, then the city alone."""
    name, addr = venue.get("name") or "", venue.get("address") or ""
    city, state = venue.get("city") or "", venue.get("state") or ""
    pin = venue.get("pincode") or ""
    tail = ", ".join(p for p in (city, state, pin, "India") if p)
    out = []
    if addr:
        out.append(f"{name}, {addr}, {tail}")
        out.append(f"{addr}, {tail}")
    out.append(f"{name}, {tail}")
    out.append(f"{city}, {state}, India" if state else f"{city}, India")
    return list(dict.fromkeys(out))


async def lookup(client: httpx.AsyncClient, query: str):
    r = await client.get(
        NOMINATIM, params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "in"}
    )
    r.raise_for_status()
    data = r.json()
    return (float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", "")) if data else None


async def main(dry_run: bool) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        venues = [dict(v) for v in await conn.fetch(
            "SELECT id, name, address, city, state, pincode FROM venues "
            "WHERE latitude IS NULL OR longitude IS NULL ORDER BY name"
        )]
        print(f"{len(venues)} venue(s) without coordinates")
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
            for v in venues:
                hit = None
                for q in queries_for(v):
                    hit = await lookup(client, q)
                    await asyncio.sleep(1.1)  # Nominatim usage policy
                    if hit:
                        break
                if not hit:
                    print(f"  ?  {v['name']} ({v['city']}): not found, stays at city centre")
                    continue
                lat, lng, shown = hit
                print(f"  ok {v['name']} ({v['city']}) -> {lat:.5f}, {lng:.5f}  [{shown[:70]}]")
                if not dry_run:
                    await conn.execute(
                        "UPDATE venues SET latitude = $2, longitude = $3, updated_at = now() WHERE id = $1",
                        v["id"], lat, lng,
                    )
    print("dry run: nothing was written" if dry_run else "done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    asyncio.run(main(ap.parse_args().dry_run))
