import asyncio
import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine

from config import settings

logger = logging.getLogger(__name__)


class SSEService:
    def __init__(self):
        self.queues: set[asyncio.Queue] = set()
        self._listener_task: asyncio.Task | None = None
        self._engine = None

    async def start(self) -> None:
        self._listener_task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
        if self._engine:
            await self._engine.dispose()

    async def subscribe(self) -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()
        self.queues.add(queue)
        try:
            while True:
                payload = await queue.get()
                yield f"data: {payload}\n\n"
        finally:
            self.queues.remove(queue)

    def _on_notify(self, connection, pid, channel, payload):
        """asyncpg callback for NOTIFY events."""
        for queue in self.queues:
            queue.put_nowait(payload)

    async def _listen(self):
        self._engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        while True:
            try:
                # We must use a dedicated connection for LISTEN
                async with self._engine.connect() as conn:
                    # asyncpg exposes the raw connection
                    raw_conn = await conn.get_raw_connection()
                    asyncpg_conn = raw_conn.driver_connection
                    await asyncpg_conn.add_listener("shoutrrr_updates", self._on_notify)

                    # Keep this connection alive and wait for cancellations
                    while True:
                        await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("SSE Listen error: %s", e)
                await asyncio.sleep(5)


sse_service = SSEService()
