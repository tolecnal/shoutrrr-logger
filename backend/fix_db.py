import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:CHANGEME@localhost:5432/shoutrrr_logger"
)
engine = create_async_engine(DATABASE_URL)


async def main():
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE notifications SET last_received_at = received_at WHERE last_received_at IS NULL"
            )
        )
        print("Fixed NULL last_received_at")


asyncio.run(main())
