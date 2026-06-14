import logging
import uuid
from typing import Any

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client

logger = logging.getLogger(__name__)


class MatrixPlugin(BasePlugin):
    @property
    def plugin_id(self) -> str:
        return "matrix"

    @property
    def name(self) -> str:
        return "Matrix"

    @property
    def description(self) -> str:
        return "Send notifications to a Matrix room."

    @property
    def default_config(self) -> dict[str, Any]:
        return {
            "homeserver_url": "https://matrix.org",
            "access_token": "",
            "room_id": "",
            "message_template": "**{title}**\n\n{message}",
        }

    async def on_notification(self, notification_dict: dict, config: dict[str, Any]) -> None:
        homeserver_url = config.get("homeserver_url", "https://matrix.org").rstrip("/")
        access_token = config.get("access_token")
        room_id = config.get("room_id")

        if not access_token or not room_id:
            logger.warning("[Matrix] Missing access_token or room_id; skipping dispatch.")
            return

        template = config.get("message_template", "**{title}**\n\n{message}")
        try:
            body = template.format(
                title=notification_dict.get("title", "No Title"),
                message=notification_dict.get("message", "No Message"),
            )
        except KeyError:
            body = template

        # Generate a unique transaction ID
        txn_id = str(uuid.uuid4())

        # Room ID needs to be properly URL encoded if we were doing it raw, but httpx can handle basic quoting if needed.
        # Actually Matrix room IDs look like !abc:domain.com, which doesn't strictly need URL quoting in the path
        # according to the spec, but usually clients quote the ! and :.
        # `httpx` handles url parsing. Let's just construct the URL:
        import urllib.parse

        encoded_room_id = urllib.parse.quote(room_id)

        url = f"{homeserver_url}/_matrix/client/v3/rooms/{encoded_room_id}/send/m.room.message/{txn_id}"

        headers = {"Authorization": f"Bearer {access_token}"}

        # Matrix allows sending formatted HTML (m.text + formatted_body) or just plain text.
        # Since the user template might be markdown, and matrix expects markdown or html,
        # we can just send it as m.text (which is plain text, but clients often parse basic markdown),
        # or we could parse it to html. Let's just send it as m.text for simplicity, or we can send
        # formatted_body with some markdown -> html if needed. We'll stick to plain text for now,
        # which many matrix clients will try to parse.
        payload = {"msgtype": "m.text", "body": body}

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            resp = await client.put(url, headers=headers, json=payload)
            resp.raise_for_status()


plugin = MatrixPlugin()
