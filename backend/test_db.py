import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:CHANGEME@localhost:5432/shoutrrr_logger"
)
engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def main():
    async with async_session() as session:
        result = await session.execute(
            text(
                "SELECT id, title, received_at, last_received_at, state FROM notifications ORDER BY received_at DESC LIMIT 5"
            )
        )
        for row in result.fetchall():
            print(row)


asyncio.run(main())
