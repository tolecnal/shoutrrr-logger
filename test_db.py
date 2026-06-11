import asyncio
from sqlalchemy import select, String, func
from database import engine
from models import Notification

async def main():
    async with engine.connect() as conn:
        stmt = select(Notification).where(Notification.tags.cast(String).ilike("%test%")).limit(1)
        res = await conn.execute(stmt)
        print("Success:", res.all())

asyncio.run(main())
