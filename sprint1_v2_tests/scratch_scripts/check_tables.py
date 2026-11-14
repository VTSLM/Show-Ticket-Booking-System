import asyncio
import sys
import os

sys.path.append(r"d:\Sem 5\Se_project\sprint1_v2\backend")
import database

async def main():
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        print("TABLES:", [r["table_name"] for r in rows])
    await database.close_pool()

if __name__ == "__main__":
    asyncio.run(main())
