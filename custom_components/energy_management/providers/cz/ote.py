import asyncio

from decimal import Decimal
from typing import Callable
from zoneinfo import ZoneInfo
from xml.etree import ElementTree
from collections.abc import AsyncGenerator
from datetime import datetime, date, time, timedelta

from ...const import TIMEZONE as UTCZONE, TIME_DAY
from ...common import ec, pg, ClientError

_TIMEZONE = ZoneInfo("Europe/Prague")
_URL_CNB = "https://api.cnb.cz/cnbapi/exrates/daily"
_URL_OTE = "https://www.ote-cr.cz/services/PublicDataService"
_QUERY_TEMPLATE = """
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:pub="http://www.ote-cr.cz/schema/service/public">
    <soapenv:Header/>
    <soapenv:Body>
        <pub:GetDamPricePeriodE>
            <pub:StartDate>{start}</pub:StartDate>
            <pub:EndDate>{end}</pub:EndDate>
            <pub:PeriodResolution>PT15M</pub:PeriodResolution>
        </pub:GetDamPricePeriodE>
    </soapenv:Body>
</soapenv:Envelope>
""".strip()

async def post(prep: Callable[[datetime, Decimal], tuple[Decimal, Decimal, Decimal]], pmod: str, currency: str, dt: datetime) -> AsyncGenerator[tuple[datetime, Decimal, Decimal], None]:
    try:
        l = dt.astimezone(_TIMEZONE).date()
        ote_resp, cnb_resp = await asyncio.gather(pg(_URL_OTE, _QUERY_TEMPLATE.format(start = (l - TIME_DAY).isoformat(), end = (l + TIME_DAY).isoformat())), pg(_URL_CNB) if currency in ("CZK", "Kč") else ec())
        root = ElementTree.fromstring(ote_resp)
    except ClientError as e:
        raise e
    except Exception as e:
        if "Application is not available" in ote_resp:
            raise Exception("OTE Application is currently not available!") from e
        raise Exception(f"Failed to parse response: {e!r}") from e

    if (fault := root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")) is not None:
        raise Exception(f"Fault: {faultstring.text if (faultstring := fault.find("faultstring")) is not None else ote_resp}")

    crate = Decimal([x for x in cnb_resp["rates"] if x["currencyCode"] == "EUR"][0]["rate"] if cnb_resp else 0)

    for item in root.findall(".//{http://www.ote-cr.cz/schema/service/public}Item"):
        indh, indm = (x // 4, (x % 4) * 15) if (x := (int(h.text) - 1) if (h := item.find("{http://www.ote-cr.cz/schema/service/public}PeriodIndex")) is not None and h.text else None) is not None else (None, None)
        idth = datetime.combine(date.fromisoformat(d.text) if (d := item.find("{http://www.ote-cr.cz/schema/service/public}Date")) is not None and d.text else None, time(0), tzinfo = _TIMEZONE).astimezone(UTCZONE) + timedelta(hours = indh, minutes = indm)
        yield idth, *prep(idth.astimezone(_TIMEZONE), ((Decimal(p.text) * crate) / Decimal(1000)) if (p := item.find(f"{{http://www.ote-cr.cz/schema/service/public}}{pmod}Price")) is not None and p.text else None)
