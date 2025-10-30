import asyncio

from typing import Callable
from decimal import Decimal
from aiohttp import ClientSession
from xml.etree import ElementTree
from collections.abc import AsyncGenerator
from datetime import datetime, date, time, timedelta

from ...const import TIMEZONE as UTCTIMEZONE, TIME_DAY
from ...common import ec, pg, ClientError

from .const import TIMEZONE

_URL_CNB = "https://api.cnb.cz/cnbapi/exrates/daily"
_URL_OTE = "https://www.ote-cr.cz/services/PublicDataService"
_QUERY_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
_QUERY_SCHEMA = "http://www.ote-cr.cz/schema/service/public"
_QUERY_TEMPLATE = f"""
<soapenv:Envelope xmlns:soapenv="{_QUERY_SOAP}" xmlns:pub="{_QUERY_SCHEMA}">
    <soapenv:Header/>
    <soapenv:Body>
        <pub:GetDamPricePeriodE>
            <pub:StartDate>{{start}}</pub:StartDate>
            <pub:EndDate>{{end}}</pub:EndDate>
            <pub:PeriodResolution>PT15M</pub:PeriodResolution>
        </pub:GetDamPricePeriodE>
    </soapenv:Body>
</soapenv:Envelope>
""".strip()

async def post(s: ClientSession, prep: Callable[[datetime, Decimal], tuple[Decimal, Decimal, Decimal]], pmod: str, currency: str, dt: datetime) -> AsyncGenerator[tuple[datetime, Decimal, Decimal], None]:
    try:
        l = dt.astimezone(TIMEZONE).date()
        ote_resp, cnb_resp = await asyncio.gather(pg(s, _URL_OTE, _QUERY_TEMPLATE.format(start = (l - TIME_DAY).isoformat(), end = (l + TIME_DAY).isoformat())), pg(s, _URL_CNB) if currency in ("CZK", "Kč") else ec())
        root = ElementTree.fromstring(ote_resp)
    except ClientError as e:
        raise e
    except Exception as e:
        if "Application is not available" in ote_resp:
            raise Exception("OTE Application is currently not available!") from e
        raise Exception(f"Failed to parse response: {e!r}") from e

    if (fault := root.find(f".//{{{_QUERY_SOAP}}}Fault")) is not None:
        raise Exception(f"Fault: {faultstring.text if (faultstring := fault.find("faultstring")) is not None else ote_resp}")

    crate = Decimal([x for x in cnb_resp["rates"] if x["currencyCode"] == "EUR"][0]["rate"] if cnb_resp else 0)

    for item in root.findall(f".//{{{_QUERY_SCHEMA}}}Item"):
        indh, indm = (x // 4, (x % 4) * 15) if (x := (int(h.text) - 1) if (h := item.find(f"{{{_QUERY_SCHEMA}}}PeriodIndex")) is not None and h.text else None) is not None else (None, None)
        idth = datetime.combine(date.fromisoformat(d.text) if (d := item.find(f"{{{_QUERY_SCHEMA}}}Date")) is not None and d.text else None, time(0), tzinfo = TIMEZONE).astimezone(UTCTIMEZONE) + timedelta(hours = indh, minutes = indm)
        yield idth, *prep(idth.astimezone(TIMEZONE), ((Decimal(p.text) * crate) / Decimal(1000)) if (p := item.find(f"{{{_QUERY_SCHEMA}}}{pmod}Price")) is not None and p.text else None)
