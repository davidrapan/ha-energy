from __future__ import annotations

import asyncio
import itertools

from typing import Any
from decimal import Decimal
from logging import getLogger
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from collections.abc import AsyncGenerator

import sqlalchemy

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_scoped_session, async_sessionmaker, AsyncSession

from homeassistant.util.dt import utcnow
from homeassistant.core import Event, HomeAssistant, callback, CALLBACK_TYPE
from homeassistant.const import ATTR_CONFIGURATION_URL, ATTR_IDENTIFIERS, ATTR_MANUFACTURER, ATTR_MODEL, ATTR_NAME, ATTR_SW_VERSION, EVENT_HOMEASSISTANT_STARTED, STATE_UNKNOWN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed, event
from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.energy.websocket_api import async_get_energy_platforms
from homeassistant.components.recorder import SupportedDialect, get_instance
from homeassistant.components.recorder.history import get_significant_states_with_session
from homeassistant.components.recorder.statistics import StatisticResult
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.sensor.recorder import compile_statistics
#from homeassistant.components.sql.sensor import _generate_lambda_stmt, _validate_and_get_session_maker_for_db_url, _async_get_or_init_domain_data
from homeassistant.components.sql.util import resolve_db_url, redact_credentials

from . import common
from .util import generate_query_string_simple, generate_query_string, generate_lambda_stmt
from .const import DOMAIN, URL, TIME_QOUR, TIME_DOUR, TIME_HOUR, TIME_DAY, ZERO_DECIMAL
from .providers import get_function

_LOGGER = getLogger(__name__)

async def _get_sessionmaker(hass: HomeAssistant) -> async_scoped_session[AsyncSession] | None:
    db_url = resolve_db_url(hass, None)
    if db_url.startswith("mysql") and not db_url.startswith("mysql+aiomysql"):
        db_url = db_url.replace("mysql", "mysql+aiomysql")
    if db_url.startswith("sqlite") and not db_url.startswith("sqlite+aiosqlite"):
        db_url = db_url.replace("sqlite", "sqlite+aiosqlite")
    if db_url.startswith("postgresql") and not db_url.startswith("postgresql+asyncpg"):
        db_url = db_url.replace("postgresql", "postgresql+asyncpg")
    try:
        maker = async_scoped_session(async_sessionmaker(bind = create_async_engine(db_url, future = True), future = True), scopefunc = asyncio.current_task)
        async with maker() as session:
            await session.execute(sqlalchemy.text("SELECT 1;"))
    except SQLAlchemyError as err:
        _LOGGER.error( "Couldn't connect using %s DB_URL: %s", redact_credentials(db_url), redact_credentials(str(err)))
        return None
    else:
        return maker

def _compile_statistics(hass: HomeAssistant, dt: datetime):
    with session_scope(hass = hass, read_only = True) as session:
        return compile_statistics(hass, session, dt - timedelta.resolution, dt).platform_stats

def _get_statistics_for_entity(statistics_results: list[StatisticResult], entity_ids: list[str] | str):
    for statistics_result in statistics_results:
        if statistics_result["meta"]["statistic_id"] in (entity_ids if isinstance(entity_ids, list) else list(entity_ids)):
            yield statistics_result

def _get_significant_states_with_session(hass: HomeAssistant, dt: datetime, entity_ids: list[str]):
    with session_scope(hass = hass, read_only = True) as session:
        return get_significant_states_with_session(hass, session, dt - TIME_QOUR, dt, entity_ids, None, True, False, True, True, True)

class CoordinatorData:
    def __init__(self, now: datetime, yesterday: dict[datetime, tuple[Decimal, Decimal, Decimal]], today: dict[datetime, tuple[Decimal, Decimal, Decimal]], tomorrow: dict[datetime, tuple[Decimal, Decimal, Decimal]], time_zone: str):
        self.now = now
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

class Coordinator(DataUpdateCoordinator[CoordinatorData]):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry[Coordinator]):
        super().__init__(hass, _LOGGER, config_entry = config_entry, name = "")
        self._data: CoordinatorData = None

        self.now: datetime | None = None
        self.battery: float | None = None
        self.battery_max: float = 100
        self.forecast: dict[datetime, float | int] = {}
        self.production: dict[datetime, float | int] = {}
        self.consumption: dict[datetime, float | int] = {}
        self.consumption_max: dict[datetime, float | int] = {}
        self.today_consumption: dict[datetime, float | int] = {}
        self.imported: dict[datetime, float | int] = {}
        self.exported: dict[datetime, float | int] = {}
        self.cost_total: dict[datetime | None, float | int] = {}
        self.cost: dict[datetime, float | int] = {}
        self.cost_today: float = None
        self.cost_rate_today: float = None
        self.predicted_cost: float = .0
        self.predicted_amortization: float = .0
        self.optimization: list[tuple[int, float, bool]] = []

        self.number_soc_max = 90
        self.number_soc_min = 20
        self.number_charge_power = 5.0
        self.number_discharge_power = 5.0

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

    async def _execute_simple(self, query_str: str):
        async with self._maker() as session:
            try:
                result = await session.execute(generate_lambda_stmt(query_str))
            except SQLAlchemyError as e:
                _LOGGER.error(f"Error executing query {query_str}: {redact_credentials(common.strepr(e))}")
                await session.rollback()
            else:
                _LOGGER.debug(f"Query: {query_str}")
                return result.scalar()

    async def _execute(self, query_str: str) -> AsyncGenerator[tuple[datetime, dict[str | Any, Any | None] | dict], None]:
        async with self._maker() as session:
            try:
                result = await session.execute(generate_lambda_stmt(query_str))
            except SQLAlchemyError as e:
                _LOGGER.error(f"Error executing query {query_str}: {redact_credentials(common.strepr(e))}")
                await session.rollback()
            else:
                _LOGGER.debug(f"Query: {query_str}")
                for k, v in itertools.zip_longest(self.consumption.keys(), [m for m in result.mappings() for _ in range(4)], fillvalue = {}):
                    if k:
                        yield k, {vk: vv / 4 if (vv := v.get(vk)) is not None else None for vk in v.keys()}

    async def _async_setup(self) -> None:
        await super()._async_setup()
        self._session = aiohttp_client.async_get_clientsession(self.hass)
        self.config_area = self.config_entry.options.get("area", "cez")
        self.config_rate = self.config_entry.options.get("rate", "D57d")
        self.config_tariff = self.config_entry.options.get("tariff", "EVV1")
        self.config_spot_hourly = self.config_entry.options.get("spot_hourly", False)
        self.config_fix_t1_id = self.config_entry.options.get("fix_t1_id", None)
        self.config_fix_t2_id = self.config_entry.options.get("fix_t2_id", None)
        self.config_cost_fee = self.config_entry.options.get("cost_fee", 0.3)
        self.config_compensation_fee = self.config_entry.options.get("compensation_fee", 0.4)
        self.config_capacity = self.config_entry.options.get("capacity", 9.7)
        self.config_amortization = self.config_entry.options.get("amortization", 2.0)
        self.config_battery_entity_ids = self.config_entry.options.get("battery_entity_ids", [])
        self.config_exclude_entity_ids = self.config_entry.options.get("exclude_entity_ids", [])
        self.config_key = self.config_entry.options.get("key", "")
        _LOGGER.debug(f"Area: {self.config_area}, rate: {self.config_rate}, tariff: {self.config_tariff}, spot_hourly: {self.config_spot_hourly}, cost_fee: {self.config_cost_fee}, compensation_fee: {self.config_compensation_fee}, capacity: {self.config_capacity}, amortization: {self.config_amortization}, battery_entity_id: {self.config_battery_entity_ids}, exclude_entity_ids {self.config_exclude_entity_ids}, key: {"***" if self.config_key else "Empty"}")
        try:
            self._energy_entries: dict[str, dict[str, list[str] | dict[str, str | None]]] = {}
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

        if self.config_fix_t1_id and (t1 := self.hass.states.get(self.config_fix_t1_id)) and t1.state == STATE_UNKNOWN:
            @callback
            async def _reload(_: Event):
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _reload)

        return self

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        if self._periodic_listener:
            self._periodic_listener()
            self._periodic_listener = None
        if self._deferred_refresh:
            self._deferred_refresh()
            self._deferred_refresh = None
        await (await self._maker.connection()).engine.dispose()

    def _get_rates_params(self, dt: datetime) -> dict[str, datetime | Decimal]:
        return {"dt": dt} | ({"T1": Decimal(t1.state if t1.state != STATE_UNKNOWN else "0")} if self.config_fix_t1_id and (t1 := self.hass.states.get(self.config_fix_t1_id)) else {}) | ({"T2": Decimal(t2.state if t2.state != STATE_UNKNOWN else "0")} if self.config_fix_t2_id and (t2 := self.hass.states.get(self.config_fix_t2_id)) else {})

    async def _fetch_data(self):
        async with asyncio.timeout(30):
            tzn = ZoneInfo(self.hass.config.time_zone)
            now = utcnow()
            self.now = common.dt_block(now)
            local = self.now.astimezone(tzn)
            today = local.date()
            get_rates, tomorrow_available = get_function(self._session, self.config_area, self.config_rate, self.config_tariff, "" if not self.config_spot_hourly else "Hourly", (self.config_cost_fee, self.config_compensation_fee), self.hass.config.country + ("" if not self.config_fix_t1_id else "-fix"), self.hass.config.currency)
            if not self.data or not self.data.tomorrow and tomorrow_available(self.now):
                yesterday_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = {}
                today_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = {}
                tomorrow_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = {}
                self.forecast.clear()
                self.production.clear()
                self.consumption.clear()
                self.consumption_max.clear()
                self.today_consumption.clear()
                async for k, i, o, v in get_rates(**self._get_rates_params(self.now)):
                    _LOGGER.debug(f"Rate at {k}: {i}, {o}, {v}")
                    l_date = k.astimezone(tzn).date()
                    if l_date == today - TIME_DAY:
                        yesterday_data[k] = (i, o, v)
                    else:
                        self.forecast[k] = 0
                        self.production[k] = None
                        self.consumption[k] = None
                        self.consumption_max[k] = None
                    if l_date == today:
                        today_data[k] = (i, o, v)
                        self.today_consumption[k] = None
                    elif l_date == today + TIME_DAY:
                        tomorrow_data[k] = (i, o, v)
            else:
                if next(iter(self.data.today)).astimezone(tzn).date() != today:
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
                        self.production[k] = None
                        self.consumption[k] = None
                        self.consumption_max[k] = None
                        self.today_consumption[k] = None
                else:
                    yesterday_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = self.data.yesterday
                    today_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = self.data.today
                    tomorrow_data: dict[datetime, tuple[Decimal, Decimal, Decimal]] = self.data.tomorrow
            self._data = CoordinatorData(self.now, yesterday_data, today_data, tomorrow_data, self.hass.config.time_zone)
            if self._energy_entries:
                production = self._energy_entries.setdefault("solar", {})
                if (solar_entries := production.get("forecast")) and (forecast_platforms := await async_get_energy_platforms(self.hass)):
                    for solar_entry_id in solar_entries:
                        if (solar_entry := self.hass.config_entries.async_get_entry(solar_entry_id)) and solar_entry is not None and solar_entry.domain in forecast_platforms and (forecast := await forecast_platforms[solar_entry.domain](self.hass, solar_entry_id)) and (wh_hours := forecast["wh_hours"]):
                            for k in self.forecast.keys():
                                if (i := k.isoformat()) and (wh_hour := wh_hours.get(i)) is not None and (q := (k + TIME_QOUR).isoformat() in wh_hours or (k - TIME_QOUR).isoformat() in wh_hours) is not None and (d := q or (k + TIME_DOUR).isoformat() in wh_hours or (k - TIME_DOUR).isoformat() in wh_hours) is not None and (f := wh_hour / 1000 / ((1 if q else 2) if d else 4)):
                                    self.forecast[k] = f
                                    _LOGGER.debug(f"Solar forecast of {solar_entry_id} for {k} ({wh_hour}): {f}")
                                    if not q:
                                        k2 = k + TIME_QOUR
                                        self.forecast[k2] = f
                                        _LOGGER.debug(f"Solar forecast of {solar_entry_id} for {k2} ({wh_hour}): {f}")
                                        if not d:
                                            k3 = k2 + TIME_QOUR
                                            self.forecast[k3] = f
                                            _LOGGER.debug(f"Solar forecast of {solar_entry_id} for {k3} ({wh_hour}): {f}")
                                            k4 = k3 + TIME_QOUR
                                            self.forecast[k4] = f
                                            _LOGGER.debug(f"Solar forecast of {solar_entry_id} for {k4} ({wh_hour}): {f}")
                grid = self._energy_entries.setdefault("grid", {})
                grid_from = grid.get("from", [])
                grid_to = grid.get("to", [])
                production_from = production.get("from", [])
                battery = self._energy_entries.setdefault("battery", {})
                battery_from = battery.get("from", [])
                battery_to = battery.get("to", [])
                registry = entity_registry.async_get(self.hass)
                battery_entities = [i for j in battery_from if (e := registry.entities.get_entries_for_device_id(registry.async_get(j).device_id)) for i in e if "battery" in (i.original_device_class, i.device_class)]
                _LOGGER.debug(f"Production: {production_from}, Grid from: {grid_from}, Grid to: {grid_to}, Battery from: {battery_from}, Battery to: {battery_to}, Battery: {battery_entities}")
                battery_ids = [j.entity_id for j in battery_entities] + self.config_battery_entity_ids  
                recorder = get_instance(self.hass)
                try:
                    if not self.consumption or next(iter(self.consumption.values())) is None or ((last_hour := common.dt_hour(self.now) - TIME_HOUR) and last_hour in self.today_consumption and self.today_consumption[last_hour] is None):
                        query_str = generate_query_string(
                            recorder.dialect_name == SupportedDialect.SQLITE,
                            common.joinify(*(grid_from + production_from + battery_from)),
                            common.joinify(*(grid_to + battery_to)),
                            common.joinify(*production_from),
                            common.joinify(*grid_from),
                            common.joinify(*grid_to),
                            common.joinify(*grid.get("cost", [])),
                            common.joinify(*grid.get("compensation", [])),
                            common.joinify(*self.config_exclude_entity_ids),
                            f"{o[:3]}:{o[3:]}" if (o := local.strftime('%z')) else "+00:00",
                            30,
                            today.weekday(),
                            (today + TIME_DAY).weekday()
                        )
                        self.imported.clear()
                        self.exported.clear()
                        self.cost.clear()
                        async for k, v in self._execute(query_str):
                            _LOGGER.debug(f"Query result {k}: {v}")
                            self.consumption[k] = c if (c := v.get("mean")) is not None else self.consumption.get(k - TIME_DAY)
                            self.consumption_max[k] = c if (c := v.get("maximum")) is not None else self.consumption_max.get(k - TIME_DAY)
                            self.today_consumption[k] = v.get("consumption")
                            self.production[k] = v.get("production")
                            self.imported[k] = v.get("imported")
                            self.exported[k] = v.get("exported")
                            self.cost[k] = v.get("cost")
                        if (cost_sum := sum(filter(None, self.cost.values()))) > 0 and (imported_sum := sum(filter(None, self.imported.values()))) > 0:
                            self.cost_today = cost_sum
                            self.cost_rate_today = cost_sum / imported_sum
                        else:
                            self.cost_today = None
                            self.cost_rate_today = None
                        if not self.now in self.cost_total:
                            self.cost_total.clear()
                            if (cost_sensors := self.hass.data["energy"]["cost_sensors"]) and (c := [cost_sensors[j] for j in grid_from]) and (all_stats := await recorder.async_add_executor_job(_compile_statistics, self.hass, now)):
                                self.cost_total[self.now] = sum(map(lambda i: i["stat"]["sum"], _get_statistics_for_entity(all_stats, c)))
                        if battery_ids:
                            self.battery_max = float(await self._execute_simple(generate_query_string_simple(recorder.dialect_name == SupportedDialect.SQLITE, common.joinify(*battery_ids), 30)))
                except Exception as e:
                    _LOGGER.debug(f"Consumption statistics error: {common.strepr(e)}")
                try:
                    if battery_ids and (stats := await recorder.async_add_executor_job(_get_significant_states_with_session, self.hass, self.now, battery_ids)):
                        self.battery = sum(map(lambda i: float(stats[i][-1]["s"]), stats)) / len(stats)
                except Exception as e:
                    _LOGGER.debug(f"Last battery state error: {common.strepr(e)}")
            if self.battery is not None and self.consumption and next(iter(self.consumption.values())):
                try:
                    keys = self._data.rates_full.keys()
                    json = {
                        "rate": [(float(self._data.rates_full[k]), 0) for k in keys if k >= self.now],
                        "production": [self.forecast[k] for k in keys if k >= self.now],
                        "consumption": [(self.consumption_max.get(self.now) or 0.2) * 1.2] + [(self.consumption.get(k) or 0.2) * 1.2 for k in keys if k > self.now],
                        "constraints": {"soc": self.battery / 100, "charge_power": self.number_charge_power / 4, "discharge_power": self.number_discharge_power / 4, "soc_min": self.number_soc_min / 100, "soc_max": (self.number_soc_max if self.battery_max > 98 else 100) / 100, "capacity": self.config_capacity, "amortization": self.config_amortization}
                    }
                    if (r := await common.pg(self._session, URL, json = json, headers = { "X-API-Key": self.config_key })) is not None:
                        _LOGGER.debug(f"Optimization of {json}: {r}")
                        self.predicted_cost = float(r[0][1])
                        self.predicted_amortization = float(r[0][3])
                        self.optimization = r[1]
                except Exception as e:
                    _LOGGER.exception(f"Optimization failed: {common.strepr(e)} ({json})")

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

        self._data.now = common.dt_block(utcnow())

        return self._data
