import asyncio
from database import engine
from sqlalchemy import select
from models import Notification
from sqlalchemy.ext.asyncio import AsyncSession
import time

async def test():
    async with AsyncSession(engine) as session:
        t0 = time.time()
        stmt = select(Notification.sender_name, Notification.tags).order_by(Notification.id.desc()).limit(1000)
        res = await session.execute(stmt)
        senders = set()
        tags = set()
        for sender, tag_list in res:
            if sender:
                senders.add(sender)
            if tag_list:
                for t in tag_list:
                    tags.add(t)
        print("Took", time.time() - t0)
        print("Senders:", senders)
        print("Tags:", tags)

asyncio.run(test())
