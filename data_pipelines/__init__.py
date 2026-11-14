"""VULPA veri katmanı (Backend / veri çekme).

Bu paket 2. yapay zekâ asistanının çalışma alanıdır. Frontend (app.py, components/) bu klasöre yazmaz;
yalnızca buradaki fonksiyonları içe aktarıp kullanır. Ayrıntılar için README.md dosyasına bakın.
"""

from .config import (
    END, GRID_LATS, GRID_LONS, GRID_STEP, LAST_FULL_YEAR, MM_CORE, MM_EXTRA, MM_URL, NOW, PERIOD, POWER_SPAN,
    POWER_URL, PROJECTION_MONTHS, START, WEATHER_TTL, hist_date,
)
from .grid import _fallback_grid, _fetch_grid, _fetch_grid_range, _fetch_historical_grid, _fetch_live_grid
from .power import MIN_TREND_YEARS, POWER_FIRST_YEAR, _fetch_power, _power_simulated, power_years
from .regions import CITY_NAMES, REGION_LIST, REGIONS, Region
from .real_series import KINDS, REAL_SOURCES, real_series, series_meta
from .credits import CREDITS, data_credits
from .annual import _fetch_grid_annual, _fetch_weather_annual
from .climatology import climatology_anomaly, expected_temp, grid_normals, normal_values, region_normals
from .series import analyze, build_series, synthetic_series
from .commands import ALLOWED_ACTIONS, parse_ui_command, switch_message, time_text
from .charts import METRICS, metric_chart
from .events import EVENT_TYPES, fetch_events
from .quality import data_quality
from .showcase import showcase_regions
from .globalstats import compare_regions, global_annual_anomaly, year_extremes
from .warmup import warm_up
from .variables import (
    VARIABLES, analyze_values, describe_point, giovanni_url, point_data, trend_tests, variable_analysis,
    variable_catalog, variable_series,
)
from .extras import GLOSSARY, data_status, glossary, region_export, season_shift, warming_ranking, warming_stripes
from .weather import (
    DELTA_FIELDS, MM_SYMBOLS, WEATHER_CODES, _fallback_weather, _fetch_historical_weather, _fetch_live_weather,
    _fetch_weather, _fetch_weather_range, _merge_mm, _open_meteo_cities, describe_code, describe_symbol,
    meteomatics_auth, meteomatics_daily_anomaly, meteomatics_now, mm_time, range_year, source_status,
)

__all__ = [
    # bölgeler
    "Region", "REGION_LIST", "REGIONS", "CITY_NAMES",
    # Meteomatics
    "meteomatics_auth", "meteomatics_now", "meteomatics_daily_anomaly", "mm_time",
    # 50 bölge hava verisi
    "_fetch_live_weather", "_fetch_historical_weather", "_fetch_weather", "_fallback_weather",
    "_open_meteo_cities", "_merge_mm", "describe_code", "describe_symbol", "WEATHER_CODES", "MM_SYMBOLS",
    # yıl aralığı (delta) — 14.11.2026
    "_fetch_weather_range", "_fetch_grid_range", "range_year", "DELTA_FIELDS",
    # belirli tarih (ay/gün) ve kaynak durumu — 14.11.2026
    "source_status",
    # veri kaynakları ve atıflar (Credits paneli)
    "data_credits", "CREDITS",
    # sene ortalaması (Frontend "Sene Ortalaması" seçeneği)
    "_fetch_weather_annual", "_fetch_grid_annual",
    # iklim normalleri (NASA POWER) — gerçekçi yedek ve "iklim normaline göre sapma"
    "region_normals", "normal_values", "expected_temp", "grid_normals", "climatology_anomaly",
    # Seiron arayüz komutları (zaman, dil, Credits, grafik) ve grafik penceresi verisi
    "parse_ui_command", "switch_message", "time_text", "ALLOWED_ACTIONS", "metric_chart", "METRICS",
    # otonom oturum (ÖNERİ #2): NASA EONET olayları — "trendi dinle" (sonify) proje sahibinin kararıyla kaldırıldı
    "fetch_events", "EVENT_TYPES", "data_quality", "showcase_regions",
    "global_annual_anomaly", "year_extremes", "compare_regions",
    "warming_stripes", "warming_ranking", "region_export", "data_status", "season_shift", "glossary", "GLOSSARY",
    # açılış ısınması (proje sahibi: "site yüklenene kadar açılmasın")
    "warm_up",
    # Büyük Plan · Aşama A: değişken seçimi, nokta analizi, t-testi, gereken yıl, Giovanni
    "VARIABLES", "variable_catalog", "variable_series", "variable_analysis", "point_data", "describe_point",
    "analyze_values", "trend_tests", "giovanni_url",
    # küresel ızgara
    "_fetch_live_grid", "_fetch_historical_grid", "_fetch_grid", "_fallback_grid",
    # NASA POWER
    "_fetch_power", "_power_simulated", "power_years", "POWER_FIRST_YEAR", "MIN_TREND_YEARS",
    # bölge tema serisi (gerçek veri → sentetik yedek) ve istatistik
    "build_series", "analyze", "synthetic_series", "series_meta", "real_series", "REAL_SOURCES", "KINDS",
    # sabitler ve zaman
    "START", "END", "PERIOD", "PROJECTION_MONTHS", "NOW", "LAST_FULL_YEAR", "POWER_SPAN", "WEATHER_TTL",
    "MM_URL", "MM_CORE", "MM_EXTRA", "POWER_URL", "GRID_STEP", "GRID_LATS", "GRID_LONS", "hist_date",
]
