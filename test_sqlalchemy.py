import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from database import engine
from repositories.notifications import NotificationRepository

async def test():
    repo = NotificationRepository()
    async with AsyncSession(engine) as session:
        q = "title:\"Memory Warning\""
        res, count, _ = await repo.search_paginated(
            session=session,
            query=q,
            cursor=None,
            page_size=10,
            scope="all",
            is_admin=True
        )
        print("Count:", count)

asyncio.run(test())
