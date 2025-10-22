from datetime import datetime, time
from functools import lru_cache
from decimal import Decimal

from ..const import TIMEZONE, TIME_DAY, PZERO_DECIMAL, RATES_DEFAULT
from .cz import get_function as get_cz

_map = {
    "CZ": get_cz
}

async def _default(dt: datetime, **kwargs: list[float]):
    t = dt.astimezone(TIMEZONE).date()
    print(t)
    r = kwargs.get("rates", RATES_DEFAULT)
    y = t - TIME_DAY
    for i in range(24):
        yield datetime.combine(y, time(i, tzinfo = dt.tzinfo)).astimezone(TIMEZONE), *((r[i], r[i]) if i < len(r) else (PZERO_DECIMAL, PZERO_DECIMAL))
    for i in range(24):
        yield datetime.combine(t, time(i, tzinfo = dt.tzinfo)).astimezone(TIMEZONE), *((r[i], r[i]) if i < len(r) else (PZERO_DECIMAL, PZERO_DECIMAL))
    t = t + TIME_DAY
    for i in range(24):
        yield datetime.combine(t, time(i, tzinfo = dt.tzinfo)).astimezone(TIMEZONE), *((r[i], r[i]) if i < len(r) else (PZERO_DECIMAL, PZERO_DECIMAL))

@lru_cache(maxsize = len(_map) + 1)
def get_function(area: str, rate: str, tariff: str, pmod: str, fee: tuple[Decimal] | Decimal, country: str, currency: str):
    return f(area, rate, tariff, fee, pmod, currency) if (f := _map.get(country)) else _default
