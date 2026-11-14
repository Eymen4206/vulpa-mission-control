"""VULPA veri katmanı (Backend / veri çekme).

Bu paket 2. yapay zekâ asistanının çalışma alanıdır. Frontend (app.py, components/) bu klasöre yazmaz;
yalnızca buradaki fonksiyonları içe aktarıp kullanır. Ayrıntılar için README.md dosyasına bakın.
"""

from .config import (
    END, GRID_LATS, GRID_LONS, GRID_STEP, LAST_FULL_YEAR, MM_CORE, MM_EXTRA, MM_URL, NOW, PERIOD, POWER_SPAN,
    POWER_URL, PROJECTION_MONTHS, START, WEATHER_TTL, hist_date,
)
from .grid import _fallback_grid, _fetch_grid, _fetch_historical_grid, _fetch_live_grid
from .power import _fetch_power, _power_simulated
from .regions import CITY_NAMES, REGION_LIST, REGIONS, Region
from .series import analyze, build_series
from .weather import (
    MM_SYMBOLS, WEATHER_CODES, _fallback_weather, _fetch_historical_weather, _fetch_live_weather, _fetch_weather,
    _merge_mm, _open_meteo_cities, describe_code, describe_symbol, meteomatics_auth, meteomatics_daily_anomaly,
    meteomatics_now, mm_time,
)

__all__ = [
    # bölgeler
    "Region", "REGION_LIST", "REGIONS", "CITY_NAMES",
    # Meteomatics
    "meteomatics_auth", "meteomatics_now", "meteomatics_daily_anomaly", "mm_time",
    # 50 bölge hava verisi
    "_fetch_live_weather", "_fetch_historical_weather", "_fetch_weather", "_fallback_weather",
    "_open_meteo_cities", "_merge_mm", "describe_code", "describe_symbol", "WEATHER_CODES", "MM_SYMBOLS",
    # küresel ızgara
    "_fetch_live_grid", "_fetch_historical_grid", "_fetch_grid", "_fallback_grid",
    # NASA POWER
    "_fetch_power", "_power_simulated",
    # sentetik seri ve istatistik
    "build_series", "analyze",
    # sabitler ve zaman
    "START", "END", "PERIOD", "PROJECTION_MONTHS", "NOW", "LAST_FULL_YEAR", "POWER_SPAN", "WEATHER_TTL",
    "MM_URL", "MM_CORE", "MM_EXTRA", "POWER_URL", "GRID_STEP", "GRID_LATS", "GRID_LONS", "hist_date",
]
