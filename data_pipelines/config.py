# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Veri katmanının ortak sabitleri ve zaman yardımcıları (app.py ile aynı değerler)."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone

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

# ── Open-Meteo arşivi (ERA5, anahtarsız) — geçmiş tarihler için hızlı yedek ───────
OM_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
RETRY_AFTER = 90   # sn: tüm kaynakların başarısız olduğu bir istek bu süre sonra yeniden denenir (önbelleğe yazılmaz)

# ── NASA POWER ───────────────────────────────────────────────────────────────
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# ── Küresel ızgara (15°) ─────────────────────────────────────────────────────
GRID_STEP = 15
GRID_LATS = np.arange(-75, 76, GRID_STEP, dtype=float)       # 11 enlem
GRID_LONS = np.arange(-180, 180, GRID_STEP, dtype=float)     # 24 boylam


def hist_date(year: int, month: int | None = None, day: int | None = None) -> datetime:
    """Zamanda yolculuk anı (12:00 UTC).

    - Yalnızca yıl: o yılda bugünün takvim günü (geriye uyumlu).
    - Ay / gün verilirse o tarih. Ay verilip gün verilmezse ayın 15'i (ay ortası).
    - Geçersiz gün ayın son gününe çekilir (31 Şubat → 28/29 Şubat). Gelecekteki bir tarih bugüne çekilir.
    """
    m = int(month) if month else NOW.month
    m = min(max(m, 1), 12)
    if day:
        d = int(day)
    elif month:
        d = 15
    else:
        d = NOW.day
    d = min(max(d, 1), calendar.monthrange(int(year), m)[1])
    when = datetime(int(year), m, d, 12, tzinfo=timezone.utc)
    if when > NOW:
        when = NOW.replace(hour=12, minute=0, second=0, microsecond=0)
        if when > NOW:
            when -= timedelta(days=1)
    return when
