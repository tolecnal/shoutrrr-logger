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
    from backend.auth import create_session_jwt

    # Find an admin user id
    async with async_session() as session:
        result = await session.execute(text("SELECT id FROM users WHERE role = 'admin' LIMIT 1"))
        row = result.fetchone()
        if row:
            jwt = create_session_jwt(str(row[0]), "admin")
            print(f"JWT={jwt}")
        else:
            print("No admin user found")


asyncio.run(main())
