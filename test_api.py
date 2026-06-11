import asyncio
import httpx
import json

async def run():
    async with httpx.AsyncClient(verify=False) as client:
        # First let's get the notifications
        # But wait, we need the token!
        pass

if __name__ == "__main__":
    asyncio.run(run())
