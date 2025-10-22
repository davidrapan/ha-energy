from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal

DOMAIN = "energy_management"

TIMEZONE = ZoneInfo("UTC")

TIME_QOUR = timedelta(minutes = 15)
TIME_HOUR = timedelta(hours = 1)
TIME_DAY = timedelta(days = 1)

TIMINGS_INTERVAL = 60
TIMINGS_UPDATE_INTERVAL = timedelta(seconds = TIMINGS_INTERVAL)

ZERO_DECIMAL = Decimal("0")
PZERO_DECIMAL = Decimal(".0")
RATES_DEFAULT = [PZERO_DECIMAL for _ in range(24)]

SQL_QUERY_TEMPLATE = """
WITH filtered AS (
    SELECT
        t.start_ts,{unixtime}
        sm.statistic_id,
        t.sum
    FROM
        statistics t
    JOIN
        statistics_meta sm ON t.metadata_id = sm.id
    WHERE
        {unixtim2} >= {date_sub} AND sm.statistic_id IN ({from_ids}, {to_ids}, 'sensor.antminer_energy', 'sensor.water_heater_energy', {cost_ids}, {compensation_ids})
),
filtered_diff AS (
    SELECT
        start_ts,
        {hour} AS hour_of_day,
        {weekday} AS day_of_week,
        statistic_id,
        COALESCE(
            sum - LAG(sum) OVER (PARTITION BY statistic_id ORDER BY start_ts),
            LEAD(sum) OVER (PARTITION BY statistic_id ORDER BY start_ts) - sum
        ) AS diff
    FROM
        filtered
),
arithmetic AS (
    SELECT
        start_ts,
        CASE WHEN day_of_week IN ({{slot}}) THEN hour_of_day ELSE hour_of_day + 24 END AS hour_of_day,
        day_of_week,
        SUM(CASE WHEN statistic_id IN ({from_ids}) THEN diff ELSE 0 END)
        - SUM(CASE WHEN statistic_id IN ({to_ids}, 'sensor.antminer_energy', 'sensor.water_heater_energy') THEN diff ELSE 0 END) as essential,
        SUM(CASE WHEN statistic_id IN ({from_ids}) THEN diff ELSE 0 END)
        - SUM(CASE WHEN statistic_id IN ({to_ids}) THEN diff ELSE 0 END) as consumption,
        SUM((CASE WHEN statistic_id IN ({prod_ids}) THEN diff ELSE 0 END)) AS production,
        SUM((CASE WHEN statistic_id IN ({grid_from}) THEN diff ELSE 0 END)) AS imported,
        SUM((CASE WHEN statistic_id IN ({grid_to}) THEN diff ELSE 0 END)) AS exported,
        SUM((CASE WHEN statistic_id IN ({cost_ids}) THEN diff ELSE 0 END)) AS cost,
        SUM((CASE WHEN statistic_id IN ({compensation_ids}) THEN diff ELSE 0 END)) AS compensation
    FROM 
        filtered_diff
    WHERE 
        day_of_week IN ({{slot}}, {{next_slot}})
    GROUP BY 
        start_ts
)
SELECT
    AVG(arithmetic.essential) AS mean,
    MIN(arithmetic.essential) AS minimum,
    MAX(arithmetic.essential) AS maximum,
    latest.consumption,
    latest.production,
    latest.imported,
    latest.exported,
    latest.cost,
    latest.compensation
FROM
    arithmetic
LEFT OUTER JOIN
    (SELECT * FROM arithmetic t WHERE DATE({unixtim2}) = DATE(CURRENT_TIMESTAMP)) AS latest ON latest.hour_of_day = arithmetic.hour_of_day
GROUP BY
    arithmetic.hour_of_day
""".strip()

SQL_QUERY_MYSQL_PARAMS = {
    "unixtime": " FROM_UNIXTIME(t.start_ts) AS unix_start_ts,",
    "unixtim2": "FROM_UNIXTIME(t.start_ts)",
    "date_sub": "DATE_SUB(CURDATE(), INTERVAL {month} MONTH)",
    "hour": "HOUR(unix_start_ts)",
    "weekday": "WEEKDAY(unix_start_ts)",
}

SQL_QUERY_SQLITE_PARAMS = {
    "unixtime": "",
    "unixtim2": "strftime('%Y-%m-%d %H:%M:%S', t.start_ts, 'unixepoch')",
    "date_sub": "strftime('%s', 'now', '-{month} month')",
    "hour": "CAST(strftime('%H', start_ts, 'unixepoch') AS INTEGER)",
    "weekday": "CAST(strftime('%w', start_ts, 'unixepoch') AS INTEGER)",
}
