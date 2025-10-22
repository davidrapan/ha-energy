from __future__ import annotations

import asyncio
import logging
import itertools

from decimal import Decimal
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from collections.abc import AsyncGenerator

from sqlalchemy import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_scoped_session, async_sessionmaker, AsyncSession

from homeassistant.core import HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.const import ATTR_CONFIGURATION_URL, ATTR_IDENTIFIERS, ATTR_MANUFACTURER, ATTR_MODEL, ATTR_NAME, ATTR_SW_VERSION
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed, event
from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.energy.websocket_api import async_get_energy_platforms
from homeassistant.components.recorder import SupportedDialect, get_instance
from homeassistant.components.recorder.history import get_significant_states_with_session
from homeassistant.components.recorder.statistics import StatisticResult
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.sensor.recorder import compile_statistics
from homeassistant.components.sql.sensor import _generate_lambda_stmt #_validate_and_get_session_maker_for_db_url, _async_get_or_init_domain_data
from homeassistant.components.sql.util import resolve_db_url, redact_credentials

from . import common
from .const import DOMAIN, TIMEZONE, TIME_QOUR, TIME_HOUR, TIME_DAY, ZERO_DECIMAL, SQL_QUERY_TEMPLATE, SQL_QUERY_MYSQL_PARAMS, SQL_QUERY_SQLITE_PARAMS
from .providers import get_function

_LOGGER = logging.getLogger(__name__)

_URL = "https://optimization.ranware.com/v0"

def gnow(tz: ZoneInfo) -> datetime:
    return datetime.now(tz).replace(minute = 0, second = 0, microsecond = 0)

class CoordinatorData:
    def __init__(self, yesterday: dict[datetime, tuple[Decimal, Decimal, Decimal]], today: dict[datetime, tuple[Decimal, Decimal, Decimal]], tomorrow: dict[datetime, tuple[Decimal, Decimal, Decimal]], time_zone: str):
        self.yesterday = yesterday
        self.today = today
        self.tomorrow = tomorrow
        self.mean = ZERO_DECIMAL
        self.zone_info = ZoneInfo(time_zone)
        self.rates: dict[datetime, Decimal] = {}
        self.rates_full: dict[datetime, Decimal] = {}
        self.compensation_rate: dict[datetime, Decimal] = {}
        self.spot_rate: dict[datetime, Decimal] = {}
        for dt, v in self.yesterday.items():
            self.rates_full[dt.astimezone(self.zone_info)] = v[0]
            self.compensation_rate[dt.astimezone(self.zone_info)] = v[1]
            self.spot_rate[dt.astimezone(self.zone_info)] = v[2]
        for dt, v in self.today.items():
            dt_local = dt.astimezone(self.zone_info)
            self.rates[dt_local] = v[0]
            self.mean += v[0]
            self.rates_full[dt_local] = v[0]
            self.compensation_rate[dt_local] = v[1]
            self.spot_rate[dt_local] = v[2]
        for dt, v in self.tomorrow.items():
            self.rates_full[dt.astimezone(self.zone_info)] = v[0]
            self.compensation_rate[dt.astimezone(self.zone_info)] = v[1]
            self.spot_rate[dt.astimezone(self.zone_info)] = v[2]
        self.mean /= len(self.today)

async def _get_sessionmaker(hass: HomeAssistant) -> async_scoped_session[AsyncSession] | None:
    db_url = resolve_db_url(hass, None)
    if db_url.startswith("mysql") and not db_url.startswith("mysql+aiomysql"):
        db_url = db_url.replace("mysql", "mysql+aiomysql")
    if db_url.startswith("sqlite") and not db_url.startswith("sqlite+aiosqlite"):
        db_url = db_url.replace("sqlite", "sqlite+aiosqlite")
    if db_url.startswith("postgresql") and not db_url.startswith("postgresql+asyncpg"):
        db_url = db_url.replace("postgresql", "postgresql+asyncpg")
    try:
        maker = async_scoped_session(async_sessionmaker(bind = create_async_engine(db_url)), scopefunc = asyncio.current_task)
        async with maker() as session:
            await session.execute(_generate_lambda_stmt("SELECT 1;"))
    except SQLAlchemyError as err:
        _LOGGER.error( "Couldn't connect using %s DB_URL: %s", redact_credentials(db_url), redact_credentials(str(err)))
        return None
    return maker

def _compile_statistics(hass: HomeAssistant, utc: datetime) -> list[StatisticResult]:
    with session_scope(hass = hass) as session:
        return compile_statistics(hass, session, utc - timedelta.resolution, utc).platform_stats

def _get_statistics_for_entity(statistics_results: list[StatisticResult], entity_ids: list[str] | str):
    for statistics_result in statistics_results:
        if statistics_result["meta"]["statistic_id"] in (entity_ids if isinstance(entity_ids, list) else list(entity_ids)):
            yield statistics_result

class Coordinator(DataUpdateCoordinator[CoordinatorData]):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry[Coordinator]):
        super().__init__(hass, _LOGGER, config_entry = config_entry, name = "")
        self._energy_entries: dict[str, dict[str, list[str] | dict[str, str | None]]] = {}
        self._maker: async_scoped_session[AsyncSession] | None = None
        self._use_database_executor: bool = False

        self._data: CoordinatorData = None

        self.battery = 0.20
        self.cost_total: dict[datetime | None, float | int] = {}

        self.forecast: dict[datetime, float | int] = {}
        self.production: dict[datetime, float | int] = {}
        self.consumption: dict[datetime, float | int] = {}
        self.consumption_max: dict[datetime, float | int] = {}
        self.today_consumption: dict[datetime, float | int] = {}
        self.imported: dict[datetime, float | int] = {}
        self.exported: dict[datetime, float | int] = {}
        self.cost: dict[datetime, float | int] = {}

        self.now_block: datetime | None = None
        self.predicted_cost: float = .0
        self.predicted_amortization: float = .0
        self.optimization: list[tuple[int, float, bool]] = []

        self.price: float = None

        self.default_service_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, config_entry.entry_id)},
            ATTR_NAME: "Energy Management",
            ATTR_MANUFACTURER: "David Rapan",
            ATTR_MODEL: "Energy Management",
            "entry_type": DeviceEntryType.SERVICE,
            #ATTR_SW_VERSION: coordinator._version,
            #ATTR_CONFIGURATION_URL: "https://ranware.com/"
        }
        #_LOGGER.warning(f"Latitude: {hass.config.latitude}, Longitude: {hass.config.longitude} Country: {hass.config.country}")

        @callback
        def action(_: datetime):
            self.config_entry.async_create_task(self.hass, self.async_refresh())

        self._periodic_listener: CALLBACK_TYPE | None = event.async_track_utc_time_change(hass, action, second = 0)
        self._deferred_refresh: CALLBACK_TYPE | None = None

    @property
    def name(self):
        return self.config_entry.title

    @name.setter
    def name(self, _: str):
        pass

    async def _get_energy_entries(self):
        sensors: dict[str, str] = self.hass.data["energy"]["cost_sensors"]
        for source in self._manager.data.get("energy_sources", {}):
            c = self._energy_entries.setdefault(source["type"], {})
            f = c.setdefault("from", [])
            t = c.setdefault("to", [])
            match source["type"]:
                case "solar":
                    if energy_from := source.get("stat_energy_from"):
                        f.append(energy_from)
                    if forecast := source.get("config_entry_solar_forecast"):
                        s = c.setdefault("forecast", {})
                        for entry in forecast:
                            s[entry] = None
                case "battery":
                    if energy_from := source.get("stat_energy_from"):
                        f.append(energy_from)
                    if energy_to := source.get("stat_energy_to"):
                        t.append(energy_to)
                case "grid":
                    for flow in source.get("flow_from", []):
                        if energy_from := flow.get("stat_energy_from"):
                            f.append(energy_from)
                            if cost := sensors.get(energy_from):
                                c.setdefault("cost", []).append(cost)
                        if energy_price := flow.get("entity_energy_price"):
                            c.setdefault("from_price", []).append(energy_price)
                    for flow in source.get("flow_to", []):
                        if energy_to := flow.get("stat_energy_to"):
                            t.append(energy_to)
                            if compensation := sensors.get(energy_to):
                                c.setdefault("compensation", []).append(compensation)
                        if energy_price := flow.get("entity_energy_price"):
                            c.setdefault("to_price", []).append(energy_price)

    async def _execute(self, query_str: str) -> AsyncGenerator[tuple[datetime, RowMapping], None]:
        async with self._maker() as session:
            try:
                result = await session.execute(_generate_lambda_stmt(query_str))
            except SQLAlchemyError as e:
                _LOGGER.error(f"Error executing query {query_str}: {redact_credentials(common.strepr(e))}")
                await session.rollback()
            else:
                _LOGGER.debug(f"Query: {query_str}")
                mappings = [m for m in result.mappings() for _ in (0, 15, 30, 45)]
                for k, v in itertools.zip_longest(self.consumption.keys(), mappings, fillvalue = {}) if len(self.consumption) > 24 * 4 else zip(self.consumption.keys(), mappings):
                    _LOGGER.debug(f"Query result {k}: {v.items()}")
                    yield k, v

    async def _async_setup(self) -> None:
        await super()._async_setup()
        self.config_area = self.config_entry.options.get("area", "CEZ")
        self.config_rate = self.config_entry.options.get("rate", "D57d")
        self.config_tariff = self.config_entry.options.get("tariff", "EVV1")
        self.config_spot_hourly = self.config_entry.options.get("spot_hourly", False)
        self.config_cost_fee = Decimal(self.config_entry.options.get("cost_fee", 0.3))
        self.config_compensation_fee = Decimal(self.config_entry.options.get("compensation_fee", 0.4))
        self.config_key = self.config_entry.options.get("key", "")
        _LOGGER.debug(f"Area: {self.config_area}, rate: {self.config_rate}, tariff: {self.config_tariff}, cost_fee: {self.config_cost_fee}, compensation_fee: {self.config_compensation_fee}, spot_hourly: {self.config_spot_hourly}")
        try:
            self._manager = await async_get_manager(self.hass)
            self._manager.async_listen_updates(self._get_energy_entries)
            if self._manager.data:
                await self._get_energy_entries()
            self._maker = await _get_sessionmaker(self.hass)
        except TimeoutError:
            raise
        except Exception as e:
            raise UpdateFailed(common.strepr(e)) from e

    async def init(self):
        await super().async_config_entry_first_refresh()
        return self

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        if self._periodic_listener:
            self._periodic_listener()
            self._periodic_listener = None
        if self._deferred_refresh:
            self._deferred_refresh()
            self._deferred_refresh = None
        try:
            await self._maker.remove()
        except Exception as e:
            _LOGGER.exception(f"Unexpected error shutting down {self.name}")

    async def _fetch_data(self):
        async with asyncio.timeout(30):
            tz = ZoneInfo(self.hass.config.time_zone)
            now = datetime.now(tz)
            today = now.date()
            if not self.data or now.hour > 13 and not self.data.tomorrow:
                yesterday_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = {}
                today_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = {}
                tomorrow_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = {}
                self.forecast.clear()
                self.production.clear()
                self.consumption.clear()
                self.consumption_max.clear()
                self.today_consumption.clear()
                async for k, i, o, v in get_function(self.config_area, self.config_rate, self.config_tariff, "" if not self.config_spot_hourly else "Hourly", (self.config_cost_fee, self.config_compensation_fee), self.hass.config.country, self.hass.config.currency)(now):
                    l = k.astimezone(tz)
                    _LOGGER.debug(f"Rate at {l} ({k}): {i}, {o}, {v}")
                    l_date = l.date()
                    if l_date == today - TIME_DAY:
                        yesterday_data[k] = (i, o, v)
                    else:
                        self.forecast[k] = 0
                        self.production[k] = 0
                        self.consumption[k] = None
                        self.consumption_max[k] = None
                    if l_date == today:
                        today_data[k] = (i, o, v)
                        self.today_consumption[k] = None
                    elif l_date == today + TIME_DAY:
                        tomorrow_data[k] = (i, o, v)
            else:
                if next(iter(self.data.today)).astimezone(tz).date() != today:
                    yesterday_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = self.data.today
                    today_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = self.data.tomorrow
                    tomorrow_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = {}
                    self.forecast.clear()
                    self.production.clear()
                    self.consumption.clear()
                    self.consumption_max.clear()
                    self.today_consumption.clear()
                    for k in today_data:
                        self.forecast[k] = 0
                        self.production[k] = 0
                        self.consumption[k] = None
                        self.consumption_max[k] = None
                        self.today_consumption[k] = None
                else:
                    yesterday_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = self.data.yesterday
                    today_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = self.data.today
                    tomorrow_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = self.data.tomorrow
            self.now_block = dt.replace(minute = (dt.minute // 15 * 15), second = 0, microsecond = 0) if (dt := datetime.now(tz)) else None
            if self._energy_entries:
                production = self._energy_entries.setdefault("solar", {})
                if (solar_entries := production.get("forecast")) and (forecast_platforms := await async_get_energy_platforms(self.hass)):
                    for solar_entry_id in solar_entries:
                        # list(today_data.keys())[-1] not in self.forecasts[solar_entry_id] and
                        if (solar_entry := self.hass.config_entries.async_get_entry(solar_entry_id)) and solar_entry is not None and solar_entry.domain in forecast_platforms and (forecast := await forecast_platforms[solar_entry.domain](self.hass, solar_entry_id)) and (wh_hours := forecast["wh_hours"]):
                            for k in self.forecast.keys():
                                if (i := k.isoformat()) and (f := wh_hours.get(i)) is not None and (f := f / 1000 / 2):
                                    _LOGGER.debug(f"Solar forecast for {k} of {solar_entry_id}: {f}")
                                    k2 = k + TIME_QOUR
                                    _LOGGER.debug(f"Solar forecast for {k2} of {solar_entry_id}: {f}")
                                    self.forecast[k] = f
                                    self.forecast[k2] = f
                battery = self._energy_entries.setdefault("battery", {})
                battery_from = battery.get("from", [])
                production_from = production.get("from", [])
                grid = self._energy_entries.setdefault("grid", {})
                grid_from = grid.get("from", [])
                grid_to = grid.get("to", [])
                query_str = SQL_QUERY_TEMPLATE.format(**(SQL_QUERY_MYSQL_PARAMS if get_instance(self.hass).dialect_name != SupportedDialect.SQLITE else SQL_QUERY_SQLITE_PARAMS),
                    from_ids = common.joinify(*(grid_from + production_from + battery_from)),
                    to_ids = common.joinify(*(grid_to + battery.get("to", []))),
                    prod_ids = common.joinify(*production_from),
                    grid_from = common.joinify(*grid_from),
                    grid_to = common.joinify(*grid_to),
                    cost_ids = common.joinify(*grid.get("cost", [])),
                    compensation_ids = common.joinify(*grid.get("compensation", []))
                ).format(
                    #month = 1, slot = now.weekday(), next_slot = (now + TIME_DAY).weekday()
                    month = 1, slot = common.weekslot(now.weekday()), next_slot = common.weekslot((now + TIME_DAY).weekday())
                )
                registry = entity_registry.async_get(self.hass)
                battery_entities = [i for j in battery_from if (e := registry.entities.get_entries_for_device_id(registry.async_get(j).device_id)) for i in e if "battery" in (i.original_device_class, i.device_class)]
                #battery_entity_states = [self.hass.states.get(i.entity_id) for i in battery_entities]
                #_LOGGER.warning(f"BATTERY: {battery_entities}: {battery_entity_states}")
                if not self.consumption or next(iter(self.consumption.values())) is None or ((last_hour := gnow(TIMEZONE) - TIME_HOUR) and last_hour in self.today_consumption and self.today_consumption[last_hour] is None):
                    self.imported.clear()
                    self.exported.clear()
                    self.cost.clear()
                    async for k, v in self._execute(query_str):
                        self.consumption[k] = c / 4 if (c := v.get("mean")) is not None else self.consumption[k - TIME_DAY]
                        self.consumption_max[k] = c / 4 if (c := v.get("maximum")) is not None else self.consumption_max[k - TIME_DAY]
                        self.today_consumption[k] = c / 4 if (c := v.get("consumption")) is not None else None
                        self.production[k] = c / 4 if (c := v.get("production")) is not None else None
                        self.imported[k] = c / 4 if (c := v.get("imported")) is not None else None
                        self.exported[k] = c / 4 if (c := v.get("exported")) is not None else None
                        self.cost[k] = c / 4 if (c := v.get("cost")) is not None else None
                    if (cost_sum := sum(filter(None, self.cost.values()))) > 0 and (imported_sum := sum(filter(None, self.imported.values()))) > 0:
                        self.price = cost_sum / imported_sum
                    else:
                        self.price = None
                    if not now in self.cost_total:
                        # if len(battery_entities) > 0:
                        #     with session_scope(hass = self.hass) as session:
                        #         utc = next(iter(self.consumption))
                        #         stats = get_significant_states_with_session(self.hass, session, utc - timedelta(hours = 1), utc, [j.entity_id for j in battery_entities], None, True, False, True, True, True)
                        #         self.battery = sum(map(lambda i: float(stats[i][-1]["s"]), stats)) / len(stats)
                        self.cost_total.clear()
                        if (cost_sensors := self.hass.data["energy"]["cost_sensors"]) and (cost := [cost_sensors[j] for j in grid_from]) and (all_statistics := await self.hass.async_add_executor_job(_compile_statistics, self.hass, now.astimezone(TIMEZONE))) and len(cost_stats := list(_get_statistics_for_entity(all_statistics, cost))) > 0:
                            self.cost_total[now] = sum(map(lambda i: i["stat"]["sum"], cost_stats))
                if len(battery_entities) > 0:
                    with session_scope(hass = self.hass) as session:
                        stats = get_significant_states_with_session(self.hass, session, self.now_block - timedelta(hours = 1), self.now_block, [j.entity_id for j in battery_entities], None, True, False, True, True, True)
                        self.battery = sum(map(lambda i: float(stats[i][-1]["s"]), stats)) / len(stats)
            data = CoordinatorData(yesterday_data, today_data, tomorrow_data, self.hass.config.time_zone)
            try:
                json = {
                    #"rate": [(v if (v := float(data.rates_full[d.astimezone(data.zone_info)])) is not None and not v.is_integer() else int(data.rates_full[d.astimezone(data.zone_info)]), v if (v := float(data.compensation_rate[d.astimezone(data.zone_info)])) is not None and not v.is_integer() else int(data.compensation_rate[d.astimezone(data.zone_info)])) for i, d in enumerate(self.consumption.keys()) if i < 192],
                    "rate": [(v if (v := float(data.rates_full[d.astimezone(data.zone_info)])) is not None and not v.is_integer() else int(data.rates_full[d.astimezone(data.zone_info)]), 0) for i, d in enumerate(self.consumption.keys()) if i < 192 and d >= self.now_block],
                    "production": [p if (p := self.production.get(k)) is not None else self.forecast[k] for k in self.forecast.keys() if k >= self.now_block],
                    #"consumption": [c - self.imported[k] + self.exported[k] if (c := self.today_consumption.get(k)) and c is not None else (self.consumption[k] * 1.20) for k in self.consumption.keys() if k >= self.now_block],
                    #"consumption": [self.consumption_max[self.now_block]] + [t if (c := self.consumption[k] * 1.20) is not None and (t := self.today_consumption.get(k)) is not None and t > c else c for k in self.consumption.keys() if k < self.now_block],
                    "consumption": [self.consumption_max[self.now_block] * 1.20] + [self.consumption[k] * 1.20 for k in self.consumption.keys() if k > self.now_block],
                    "constraints": {"soc": self.battery / 100, "charge_power": 5.0 / 4, "discharge_power": 5.0 / 4, "soc_min": 0.20, "soc_max": 0.90, "capacity": 9.7, "amortization": 2.0}
                }
                if (r := await common.pg(_URL, json = json, headers = { "X-API-Key": self.config_key })) is not None:
                    _LOGGER.debug(f"Optimization of {json}: {r}")
                    self.predicted_cost = float(r[0][1])
                    self.predicted_amortization = float(r[0][3])
                    self.optimization = r[1]
            except Exception:
                _LOGGER.exception(f"Optimization failed: {json}")
            self._data = data

    async def _async_update_data(self):

        async def action(_: datetime):
            if self._deferred_refresh:
                self._deferred_refresh()
                self._deferred_refresh = None
            await self._fetch_data()

            #async def action():
            #    self.async_set_updated_data(await self._fetch_data())

            #self.config_entry.async_create_background_task(self.hass, action(), name = f"{self.name} - {self.config_entry.title} - deferred refresh", eager_start = False)

        if self._data:
            self._deferred_refresh = event.async_call_later(self.hass, 30, action)
        else:
            await self._fetch_data()
        return self._data
