import logging

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import database
from database import get_db


@pytest.mark.parametrize("status_code", [401, 403, 404, 422])
async def test_get_db_does_not_log_error_for_client_http_exceptions(
    engine, monkeypatch, caplog, status_code
):
    """4xx HTTPExceptions are normal control flow, not errors worth a traceback."""
    monkeypatch.setattr(
        database, "async_session_factory", async_sessionmaker(engine, class_=AsyncSession)
    )

    with caplog.at_level(logging.ERROR, logger="database"):
        gen = get_db()
        await anext(gen)
        with pytest.raises(HTTPException):
            await gen.athrow(HTTPException(status_code=status_code, detail="boom"))

    assert caplog.records == []


async def test_get_db_logs_error_for_server_http_exceptions(engine, monkeypatch, caplog):
    """5xx HTTPExceptions are genuine failures and should be logged as errors."""
    monkeypatch.setattr(
        database, "async_session_factory", async_sessionmaker(engine, class_=AsyncSession)
    )

    with caplog.at_level(logging.ERROR, logger="database"):
        gen = get_db()
        await anext(gen)
        with pytest.raises(HTTPException):
            await gen.athrow(HTTPException(status_code=500, detail="boom"))

    assert any(r.levelno == logging.ERROR for r in caplog.records)


async def test_get_db_logs_error_for_unexpected_exceptions(engine, monkeypatch, caplog):
    monkeypatch.setattr(
        database, "async_session_factory", async_sessionmaker(engine, class_=AsyncSession)
    )

    with caplog.at_level(logging.ERROR, logger="database"):
        gen = get_db()
        await anext(gen)
        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("boom"))

    assert any(r.levelno == logging.ERROR for r in caplog.records)
