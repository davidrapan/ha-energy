from functools import cache, partial
from aiohttp import ClientSession
from datetime import datetime
from decimal import Decimal
from math import trunc

from ...common import fruple
from .const import VAT, TIMEZONE, RATE, TARIFF
from .ote import post

@cache
def _get_tariff(tariff: tuple[tuple[int | float, int | float]] | list[tuple[tuple[int | float, int | float]]], weekday: int, hour: int | float):
    for start, end in tariff if isinstance(tariff, tuple) else tariff[weekday]:
        if start <= hour < end:
            return "T2"
    return "T1"

@cache
def _get_distribution(area: str, rate: str, tariff: str, year: int, weekday: int, hour: int | float) -> Decimal:
    return RATE[year][""] + RATE[year][area][rate][_get_tariff(RATE[year][area][rate]["Type"][tariff[-2:]] if "Type" in RATE[year][area][rate] and tariff in TARIFF and RATE[year][area][rate]["Name"] == tariff[:-2] else (), weekday, hour)]

@cache
def _get_distribution_function(area: str, rate: str, tariff: str):
    return partial(_get_distribution, area, rate, tariff)

@cache
def _get_final_pricing(area: str, rate: str, tariff: str, fee: tuple[float | Decimal] | float | Decimal, dt: datetime, price: Decimal):
    return (_get_distribution_function(area, rate, tariff)(dt.year, dt.weekday(), round(dt.hour + trunc(dt.minute / 6) / 10, 1)) + price + Decimal(fruple(fee))) * (1 + VAT), price - Decimal(fruple(fee, -1)), price * (1 + VAT)

@cache
def _get_final_pricing_function(area: str, rate: str, tariff: str, fee: tuple[float | Decimal] | float | Decimal):
    return partial(_get_final_pricing, area, rate, tariff, fee)

@cache
def get_function(s: ClientSession, area: str, rate: str, tariff: str, fee: tuple[float | Decimal] | float | Decimal, pmod: str, currency: str):
    return partial(post, s, _get_final_pricing_function(area, rate, tariff, fee), pmod, currency), lambda dt: dt.astimezone(TIMEZONE).hour > 12
