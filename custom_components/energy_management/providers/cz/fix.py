from decimal import Decimal
from aiohttp import ClientSession
from typing import Callable, Coroutine
from collections.abc import AsyncGenerator
from datetime import datetime, date, time, timedelta

from homeassistant.util.dt import UTC, utcnow

from ...const import TIME_DAY

from .const import TIMEZONE

async def post(_: ClientSession, prep: Callable[[datetime, Decimal | tuple[Decimal, Decimal]], Coroutine[None, None, tuple[Decimal, Decimal, Decimal]]], _pmod: str, _currency: str, **kwargs: datetime | Decimal) -> AsyncGenerator[tuple[datetime, Decimal, Decimal], None]:
    l: date = (kwargs.get("dt", utcnow())).astimezone(TIMEZONE).date()
    t1 = kwargs.get("T1", 0)
    t2 = kwargs.get("T2", t1)
    y = datetime.combine(l - TIME_DAY, time(0), tzinfo = TIMEZONE).astimezone(UTC)
    for i in range(96):
        indh, indm = (i // 4, (i % 4) * 15)
        idth = y + timedelta(hours = indh, minutes = indm)
        yield idth, *await prep(idth.astimezone(TIMEZONE), (t1, t2))
    t = datetime.combine(l, time(0), tzinfo = TIMEZONE).astimezone(UTC)
    for i in range(96):
        indh, indm = (i // 4, (i % 4) * 15)
        idth = t + timedelta(hours = indh, minutes = indm)
        yield idth, *await prep(idth.astimezone(TIMEZONE), (t1, t2))
    t = datetime.combine(l + TIME_DAY, time(0), tzinfo = TIMEZONE).astimezone(UTC)
    for i in range(96):
        indh, indm = (i // 4, (i % 4) * 15)
        idth = t + timedelta(hours = indh, minutes = indm)
        yield idth, *await prep(idth.astimezone(TIMEZONE), (t1, t2))
