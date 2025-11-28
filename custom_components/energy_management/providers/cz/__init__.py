import asyncio
import re

from logging import getLogger
from functools import cache, partial
from datetime import datetime, date, time
from aiohttp import ClientSession
from decimal import Decimal

from ...common import strepr, fruple, pg
from .const import VAT, TIMEZONE, RATE, TARIFF, URL_CEZ, CEZ_TUPLES, URL_EGD_REGION, URL_EGD
from .ote import post

_LOGGER = getLogger(__name__)

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
        case "west" | "západ":
            region = "zapad"
        case "north":
            region = "sever"
        case "center" | "střed":
            region = "stred"
        case "east" | "východ":
            region = "vychod"
        case "moravia":
            region = "morava"
    for x in ["zapad", "sever", "stred", "vychod", "morava"]:
        if x in region:
            return x

@acache
async def _get_intervals(s: ClientSession, area: str, rate: str, tariff: str, _: date):
    try:
        match area:
            case "CEZ" if ';' in tariff:
                region, code = tariff.split(";")
                data = (await pg(s, URL_CEZ.format(_region_normalized(region), code.upper())))["data"]
                resp = tuple(tuple((time(hour = int(o[0]), minute = int(o[1])), time(hour = int(f[0]), minute = int(f[1]))) for on, off in CEZ_TUPLES if d[on] and (o := d[on].split(":")) and (f := d[off].split(":"))) for d in data)
                if _all_same(resp):
                    return resp[0]
                if len(resp) == 2:
                    w, e = (resp[1], resp[0]) if data[0]["PLATNOST"] == "So - Ne" else (resp[0], resp[1])
                    return (w, w, w, w, w, e, e)
                return resp
            case "EGD":
                region, code = tariff.split(';') if ';' in tariff else ("", tariff)
                if region.isnumeric():
                    region = [x for x in await pg(s, URL_EGD_REGION) if x["PSC"] == region][0]["Region"]
                code_a, code_b, code_p = (regex.group(1), regex.group(2), regex.group(4)) if (regex := re.search("A(\\d+)B(\\d+)(DP|P)(\\d+)", code, re.IGNORECASE)) and len(regex.groups()) > 3 else (code, code, code)
                data = await pg(s, URL_EGD)
                resp = tuple(tuple((time(hour = int(o[0]), minute = int(o[1])), time(hour = int(f[0]), minute = int(f[1]))) for c in s["casy"] if (o := c["od"].split(":")) and (f := c["do"].split(":"))) for s in [r for r in [d for d in data if (not region and d["kodHdo_A"] == code_a) or (d["region"] == region and d['A'] == code_a and d['B'] == code_b and (d["DP"] == code_p or d["DP"] == '0' + code_p))][0]["sazby"] if rate in r["sazba"]][0]["dny"])
                if _all_same(resp):
                    return resp[0]
                return resp
    except Exception as e:
        _LOGGER.debug(f"Tariff intervals error: {strepr(e)}")
    return None

@cache
def _get_tariff(tariff: tuple[tuple[time, time]] | tuple[tuple[tuple[time, time]]], weekday: int, t: time):
    if tariff:
        for start, end in tariff if tariff[0] and isinstance(tariff[0][0], time) else tariff[weekday]:
            if start <= t < end:
                return "T2"
    return "T1"

@acache
async def _get_distribution(s: ClientSession, area: str, rate: str, tariff: str, dt: datetime) -> Decimal:
    return RATE[dt.year][""] + RATE[dt.year][area][rate][_get_tariff(RATE[dt.year][area][rate]["Type"][tariff[-2:]] if "Type" in RATE[dt.year][area][rate] and tariff in TARIFF and RATE[dt.year][area][rate]["Name"] == tariff[:-2] else TARIFF[tariff] if tariff in TARIFF else await _get_intervals(s, area, rate, tariff, dt.date()), dt.weekday(), dt.time())]

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
