from datetime import datetime
from typing import Any, Iterable
from aiohttp import ClientSession, ClientError, ContentTypeError

from homeassistant.util import slugify as _slugify

def dt_block(dt: datetime):
    return dt.replace(minute = (dt.minute // 15 * 15), second = 0, microsecond = 0)

def dt_block_index(dt: datetime):
    return dt.hour * 4 + dt.minute // 15

def dt_hour(dt: datetime):
    return dt.replace(minute = 0, second = 0, microsecond = 0)

def strepr(value: Any) -> str:
    return s if (s := str(value)) else repr(value)

def fruple(value: Any, index: int = 0):
    return value[index] if isinstance(value, tuple) else value

def slugify(*items: Iterable[str | None], separator: str = "_") -> str:
    return _slugify(separator.join(filter(None, items)), separator = separator)

def joinify(*items: Iterable[str | None], separator: str = ", ") -> str:
    return separator.join(filter(None, map(lambda id: f"'{id}'", items))) or "''"

def weekslot(day_of_week: int):
    return "0, 1, 2, 3, 4" if day_of_week < 5 else "5, 6"

async def pg(s: ClientSession, url: str, data: Any | None = None, json: Any | None = None, params: Any | None = None, headers: dict | None = None) -> str | Any:
    try:
        async with (s.post if data is not None or json is not None else s.get)(url, data = data, json = json, params = params, headers = headers) as r:
            match r.content_type:
                case "text/plain" | "text/html" | "text/xml":
                    return await r.text()
                case "application/json":
                    return await r.json()
                case _:
                    raise ContentTypeError(r.request_info, r.history, status = r.status, message = "Attempt to decode unexpected mimetype", headers = r.headers)
    except ClientError as e:
        raise e

async def ec():
    pass
