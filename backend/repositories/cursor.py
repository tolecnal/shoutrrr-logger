"""Opaque keyset-pagination cursors.

A cursor encodes the ``(sort_timestamp, id)`` of the last row on the
previous page, so the next page can be fetched with
``WHERE (sort_col, id) < (cursor_ts, cursor_id)`` instead of an ``OFFSET`` —
this keeps deep pagination over large tables cheap (index range scan rather
than skipping ``offset`` rows).
"""

import base64
import uuid
from datetime import datetime

from fastapi import HTTPException, status


def encode_cursor(ts: datetime, row_id: uuid.UUID) -> str:
    raw = f"{ts.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, id_str = raw.rsplit("|", 1)
        return datetime.fromisoformat(ts_str), uuid.UUID(id_str)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pagination cursor"
        ) from exc
