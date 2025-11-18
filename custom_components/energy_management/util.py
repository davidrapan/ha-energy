from functools import cache
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy import lambda_stmt
from sqlalchemy.util import LRUCache
from sqlalchemy.sql.lambdas import StatementLambdaElement

from .const import *
from .common import *

_SQL_LAMBDA_CACHE: LRUCache = LRUCache(1000)

@cache
def generate_query_string(
    is_sqlite: bool,
    from_ids: str,
    to_ids: str,
    prod_ids: str,
    grid_from: str,
    grid_to: str,
    cost_ids: str,
    compensation_ids: str,
    exclude_ids: str,
    offset: str,
    month: int,
    weekday: int,
    next_weekday: int
) -> str:
    return SQL_QUERY_TEMPLATE.format(
        **(SQL_QUERY_MYSQL_PARAMS if not is_sqlite else SQL_QUERY_SQLITE_PARAMS),
        from_ids = from_ids,
        to_ids = to_ids,
        prod_ids = prod_ids,
        grid_from = grid_from,
        grid_to = grid_to,
        cost_ids = cost_ids,
        compensation_ids = compensation_ids,
        exclude_ids = exclude_ids
    ).format(
        offset = offset,
        month = month,
        slot = weekslot(weekday), next_slot = weekslot(next_weekday) # slot = weekday, next_slot = next_weekday
    )

def generate_lambda_stmt(query: str) -> StatementLambdaElement:
    """Generate the lambda statement."""
    t = text(query)
    return lambda_stmt(lambda: t, lambda_cache = _SQL_LAMBDA_CACHE)
