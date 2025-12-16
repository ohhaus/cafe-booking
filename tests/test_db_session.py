import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_db_session(db_session):  # noqa
    result = await db_session.execute(text('SELECT 1'))
    assert result.scalar() == 1
