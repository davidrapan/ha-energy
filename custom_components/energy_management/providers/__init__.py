from datetime import datetime, time
from aiohttp import ClientSession
from functools import lru_cache
from decimal import Decimal

from homeassistant.util.dt import UTC

from ..const import TIME_DAY, PZERO_DECIMAL, RATES_DEFAULT
from .cz import get_function as get_cz

_map = {
    "CZ": get_cz
}

async def _default(dt: datetime, **kwargs: list[float]):
    t = dt.astimezone(UTC).date()
    print(t)
    r = kwargs.get("rates", RATES_DEFAULT)
    y = t - TIME_DAY
    for i in range(24):
        yield datetime.combine(y, time(i, tzinfo = dt.tzinfo)).astimezone(UTC), *((r[i], r[i]) if i < len(r) else (PZERO_DECIMAL, PZERO_DECIMAL))
    for i in range(24):
        yield datetime.combine(t, time(i, tzinfo = dt.tzinfo)).astimezone(UTC), *((r[i], r[i]) if i < len(r) else (PZERO_DECIMAL, PZERO_DECIMAL))
    t = t + TIME_DAY
    for i in range(24):
        yield datetime.combine(t, time(i, tzinfo = dt.tzinfo)).astimezone(UTC), *((r[i], r[i]) if i < len(r) else (PZERO_DECIMAL, PZERO_DECIMAL))

def _get_default(_: ClientSession, _area: str, _rate: str, _tariff: str, _fee: tuple[float | Decimal] | float | Decimal, _pmod: str, _currency: str):
    return _default, lambda _: False

@lru_cache(maxsize = len(_map) + 1)
def get_function(s: ClientSession, area: str, rate: str, tariff: str, pmod: str, fee: tuple[float | Decimal] | float | Decimal, country: str, currency: str):
    return _map.get(country, _get_default)(s, area, rate, tariff, fee, pmod, currency)
