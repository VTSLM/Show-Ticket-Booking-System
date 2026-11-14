import asyncio
import asyncpg

async def check():
    url = 'postgresql://postgres.nvgghebapzhxzrwunwrj:IT314SoftwareEngineering@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
    try:
        conn = await asyncpg.connect(url, ssl='require', timeout=10)
        events_cols = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'events'
            ORDER BY ordinal_position;
        """)
        print('Events columns:', [(r['column_name'], r['data_type']) for r in events_cols])
        venues_cols = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'venues'
            ORDER BY ordinal_position;
        """)
        print('Venues columns:', [(r['column_name'], r['data_type']) for r in venues_cols])
        await conn.close()
    except Exception as e:
        print('DB check error:', e)

if __name__ == '__main__':
    asyncio.run(check())
