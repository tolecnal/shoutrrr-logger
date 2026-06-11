import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.config import settings
from backend.models import AccessToken
from backend.services.notifications import notification_service

engine = create_async_engine(settings.database_url)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def run():
    async with async_session_factory() as session:
        token = (await session.execute(select(AccessToken).limit(1))).scalar_one_or_none()
        try:
            notif = await notification_service.store_incoming(
                session,
                token=token,
                sender_name="jeh-test",
                title="Test1",
                message="Test notification1",
                raw_payload=None,
                source_ip="127.0.0.1",
                severity="info",
                tags=[],
                fingerprint_group=None
            )
            await session.commit()
            print("Successfully inserted notification:", notif.id)
        except Exception as e:
            print("Error inserting notification:", e)

if __name__ == "__main__":
    asyncio.run(run())
