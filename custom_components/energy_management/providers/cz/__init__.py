import asyncio

from functools import cache, partial
from datetime import datetime, date, time
from aiohttp import ClientSession
from decimal import Decimal

from ...common import fruple, pg
from .const import VAT, TIMEZONE, RATE, TARIFF, URL_CEZ, CEZ_TUPLES
from .ote import post

def acache(function):
    @cache
    def cached_function(*args, **kwargs):
        return asyncio.ensure_future(function(*args, **kwargs))
    return cached_function

def _all_same(values):
    return all(i == values[0] for i in values)

@cache
def _area_normalized(area: str):
    area = area.upper()
    match area:
        case "ČEZ":
            return "CEZ"
        case "EG.D":
            return "EGD"
        case "PREDISTRIBUCE":
            return "PRE"
    return area   

@cache
def _region_normalized(region: str):
    region = region.lower()
    match region:
        case "west":
            region = "zapad"
        case "north":
            region = "sever"
        case "center":
            region = "stred"
        case "east":
            region = "vychod"
        case "moravia":
            region = "morava"
    for x in ["zapad", "sever", "stred", "vychod", "morava"]:
        if x in region:
            return x

@acache
async def _get_intervals(s: ClientSession, tariff: str, _: date):
    region, code = tariff.split(";")
    data = (await pg(s, URL_CEZ.format(_region_normalized(region), code.upper())))["data"]
    resp = tuple(tuple((time(hour = int(o[0]), minute = int(o[1])), time(hour = int(f[0]), minute = int(f[1]))) for on, off in CEZ_TUPLES if d[on] and (o := d[on].split(":")) and (f := d[off].split(":"))) for d in data)
    if _all_same(resp):
        return resp[0]
    if len(resp) == 2:
        w, e = (resp[1], resp[0]) if data[0]["PLATNOST"] == "So - Ne" else (resp[0], resp[1])
        return (w, w, w, w, w, e, e)
    return resp

@cache
def _get_tariff(tariff: tuple[tuple[time, time]] | tuple[tuple[tuple[time, time]]], weekday: int, t: time):
    for start, end in tariff if tariff[0] and isinstance(tariff[0][0], time) else tariff[weekday]:
        if start <= t < end:
            return "T2"
    return "T1"

@acache
async def _get_distribution(s: ClientSession, area: str, rate: str, tariff: str, dt: datetime) -> Decimal:
    return RATE[dt.year][""] + RATE[dt.year][area][rate][_get_tariff(RATE[dt.year][area][rate]["Type"][tariff[-2:]] if "Type" in RATE[dt.year][area][rate] and tariff in TARIFF and RATE[dt.year][area][rate]["Name"] == tariff[:-2] else TARIFF[tariff] if tariff in TARIFF else await _get_intervals(s, tariff, dt.date()), dt.weekday(), dt.time())]

@cache
def _get_distribution_function(s: ClientSession, area: str, rate: str, tariff: str):
    return partial(_get_distribution, s, _area_normalized(area), rate, tariff)

@acache
async def _get_final_pricing(s: ClientSession, area: str, rate: str, tariff: str, fee: tuple[float | Decimal] | float | Decimal, dt: datetime, price: Decimal):
    return (await _get_distribution_function(s, area, rate, tariff)(dt) + price + Decimal(fruple(fee))) * (1 + VAT), price - Decimal(fruple(fee, -1)), price * (1 + VAT)

@cache
def _get_final_pricing_function(s: ClientSession, area: str, rate: str, tariff: str, fee: tuple[float | Decimal] | float | Decimal):
    return partial(_get_final_pricing, s, area, rate, tariff, fee)

@cache
def get_function(s: ClientSession, area: str, rate: str, tariff: str, fee: tuple[float | Decimal] | float | Decimal, pmod: str, currency: str):
    return partial(post, s, _get_final_pricing_function(s, area, rate, tariff, fee), pmod, currency), lambda dt: dt.astimezone(TIMEZONE).hour > 12
