"""Veri katmanının ortak sabitleri ve zaman yardımcıları (app.py ile aynı değerler)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

# ── Sentetik seri ve istatistik ──────────────────────────────────────────────
START = "2000-01-01"
END = "2024-12-01"
ALPHA = 0.05
PERIOD = 12
PROJECTION_MONTHS = 120

# ── Zaman ────────────────────────────────────────────────────────────────────
NOW = datetime.now(timezone.utc)
LAST_FULL_YEAR = NOW.year - 1                      # NASA POWER için son tamamlanmış yıl
POWER_SPAN = 20                                    # uzun vadeli trend penceresi (yıl)

# ── Önbellek ─────────────────────────────────────────────────────────────────
WEATHER_TTL = 1800  # 30 dakika: termal, basınç ve rüzgâr verileri bu aralıkla otomatik yenilenir

# ── Meteomatics ──────────────────────────────────────────────────────────────
MM_URL = "https://api.meteomatics.com"
MM_CORE = ("t_2m:C", "msl_pressure:hPa", "wind_speed_10m:ms", "wind_dir_10m:d")
MM_EXTRA = ("relative_humidity_2m:p", "weather_symbol_1h:idx")

# ── NASA POWER ───────────────────────────────────────────────────────────────
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# ── Küresel ızgara (15°) ─────────────────────────────────────────────────────
GRID_STEP = 15
GRID_LATS = np.arange(-75, 76, GRID_STEP, dtype=float)       # 11 enlem
GRID_LONS = np.arange(-180, 180, GRID_STEP, dtype=float)     # 24 boylam


def hist_date(year: int) -> datetime:
    """Seçilen yılda bugünün takvim gününe denk gelen an (12:00 UTC). 29 Şubat → 28 Şubat."""
    day = 28 if (NOW.month, NOW.day) == (2, 29) else NOW.day
    return datetime(year, NOW.month, day, 12, tzinfo=timezone.utc)
