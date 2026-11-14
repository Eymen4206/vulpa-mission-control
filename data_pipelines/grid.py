"""15°'lik küresel meteoroloji ızgarası (11 × 24) — termal alan, izobarlar ve rüzgâr vektörleri için ham veri.

app.py içindeki fonksiyonların birebir kopyası. Görselleştirme katmanı (grid_layers, _resample,
_contour_segments, renk durakları) app.py'de kalır.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import requests
import streamlit as st

from .config import GRID_LATS, GRID_LONS, GRID_STEP, MM_CORE, WEATHER_TTL, hist_date
from .weather import DELTA_FIELDS, meteomatics_daily_anomaly, meteomatics_now, mm_time, range_source, range_year

def _fallback_grid() -> dict:
    """Ağ yoksa: genel dolaşıma dayalı, açıkça 'tahmini' etiketli kuşaksal alanlar."""
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    alat = np.abs(la)
    pressure = 1010 + 10 * np.exp(-((alat - 30) / 10) ** 2) - 12 * np.exp(-((alat - 60) / 8) ** 2) \
        + 3 * np.cos(np.radians(lo * 3))
    wind_dir = np.where(alat < 30, 90.0, np.where(alat < 60, 270.0, 90.0))
    return {"live": False, "time": datetime.now(timezone.utc).strftime("%H:%M"), "source": "simülasyon",
            "temp": 27 - 0.45 * alat, "anomaly": np.zeros_like(la), "pressure": pressure,
            "wind": np.full_like(la, 15.0), "wind_dir": wind_dir}


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_historical_grid(year: int) -> dict:
    """Seçilen yılın aynı takvim günü için Meteomatics arşiv ızgarası (anlık alanlar + 30 günlük sapma)."""
    when = hist_date(year)
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    out = _fallback_grid()
    out["time"] = when.strftime("%d.%m.%Y %H:%M")
    box = (f"{GRID_LATS[-1]:g},{GRID_LONS[0]:g}_{GRID_LATS[0]:g},{GRID_LONS[-1]:g}:"
           f"{GRID_STEP:g},{GRID_STEP:g}")
    keys = [(float(a), float(b)) for a, b in zip(la.ravel(), lo.ravel())]
    try:
        mm, _ = meteomatics_now(MM_CORE, box, timeout=25, when=mm_time(when))
        for param, name, scale in (("t_2m:C", "temp", 1.0), ("msl_pressure:hPa", "pressure", 1.0),
                                   ("wind_speed_10m:ms", "wind", 3.6), ("wind_dir_10m:d", "wind_dir", 1.0)):
            arr = np.array([mm[param].get(k) for k in keys], dtype=float)
            if np.isnan(arr).any():
                raise ValueError("eksik Meteomatics ızgarası")
            out[name] = arr.reshape(la.shape) * scale
        out.update({"live": True, "source": "Meteomatics"})
    except Exception:
        return out
    try:
        anom = meteomatics_daily_anomaly(box, when, timeout=30)
        out["anomaly"] = np.array([anom.get(k) if anom.get(k) is not None else 0.0 for k in keys],
                                  dtype=float).reshape(la.shape)
    except Exception:
        pass
    return out


def _fetch_grid(start_year: int = 0, end_year: int | None = None) -> dict:
    """15° küresel ızgara.

    - Tek yıl (geriye uyumlu): `_fetch_grid(year)` → 0 canlı, aksi halde o yılın bugünkü takvim günü.
    - Yıl aralığı: `_fetch_grid(start_year, end_year)` → bitiş yılının alanları + `temp_delta`,
      `pressure_delta`, `wind_delta` (bitiş − başlangıç, numpy 11×24).
    """
    if end_year is None:
        return _fetch_historical_grid(start_year) if start_year else _fetch_live_grid()
    return _fetch_grid_range(int(start_year), int(end_year))


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_grid_range(start_year: int, end_year: int) -> dict:
    """İki yılın aynı takvim günü için ızgara alanları ve farkları. İstisna fırlatmaz; uçlardan biri
    simülasyonsa `delta_live` False olur."""
    sy, ey = range_year(start_year), range_year(end_year)
    s = _fetch_historical_grid(sy)
    e = _fetch_historical_grid(ey)
    out = dict(e)
    for f in DELTA_FIELDS:
        out[f"{f}_start"] = s[f]
        out[f"{f}_delta"] = np.round(np.asarray(e[f], dtype=float) - np.asarray(s[f], dtype=float), 2)
    both = s["live"] and e["live"]
    out.update({"range": True, "start_year": sy, "end_year": ey, "start_time": s["time"], "end_time": e["time"],
                "start_live": s["live"], "end_live": e["live"], "delta_live": both,
                "source": range_source("Meteomatics", s, e)})
    return out


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_live_grid() -> dict:
    """15°'lik küresel ızgara (264 nokta).

    Anlık sıcaklık, deniz seviyesi basıncı ve 10 m rüzgârı Meteomatics ızgara sorgusundan
    (75,-180_-75,165:15,15) gelir; son 30 günün günlük ortalamaları (termal anomali) Open-Meteo'dan.
    Biri başarısız olursa diğeri, ikisi de başarısız olursa kuşaksal simülasyon kullanılır. 30 dk önbellek.
    """
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    shape = la.shape
    out = _fallback_grid()
    sources = []
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": ",".join(f"{v:g}" for v in la.ravel()),
                    "longitude": ",".join(f"{v:g}" for v in lo.ravel()),
                    "current": "temperature_2m,pressure_msl,wind_speed_10m,wind_direction_10m",
                    "daily": "temperature_2m_mean", "past_days": 30, "forecast_days": 1, "timezone": "UTC"},
            timeout=20,
        )
        resp.raise_for_status()
        items = resp.json()
        if not isinstance(items, list) or len(items) != la.size:
            raise ValueError("eksik ızgara yanıtı")
        temp, anom, pres, wind, wdir = (np.zeros(la.size) for _ in range(5))
        for k, item in enumerate(items):
            cur = item["current"]
            temp[k] = cur["temperature_2m"]
            pres[k] = cur["pressure_msl"]
            wind[k] = cur["wind_speed_10m"] or 0.0
            wdir[k] = cur["wind_direction_10m"] or 0.0
            means = [v for v in item.get("daily", {}).get("temperature_2m_mean", []) if v is not None]
            anom[k] = means[-1] - float(np.mean(means[:-1])) if len(means) >= 8 else 0.0
        out.update({"live": True, "time": items[0]["current"]["time"][-5:], "temp": temp.reshape(shape),
                    "anomaly": anom.reshape(shape), "pressure": pres.reshape(shape),
                    "wind": wind.reshape(shape), "wind_dir": wdir.reshape(shape)})
        sources.append("Open-Meteo")
    except Exception:
        pass
    try:
        top, bottom = GRID_LATS[-1], GRID_LATS[0]
        west, east = GRID_LONS[0], GRID_LONS[-1]
        mm, stamp = meteomatics_now(MM_CORE, f"{top:g},{west:g}_{bottom:g},{east:g}:{GRID_STEP:g},{GRID_STEP:g}",
                                    timeout=20)
        fields = {}
        for param, name, scale in (("t_2m:C", "temp", 1.0), ("msl_pressure:hPa", "pressure", 1.0),
                                   ("wind_speed_10m:ms", "wind", 3.6), ("wind_dir_10m:d", "wind_dir", 1.0)):
            arr = np.array([mm[param].get((float(a), float(b))) for a, b in zip(la.ravel(), lo.ravel())],
                           dtype=float)
            if np.isnan(arr).any():
                raise ValueError("eksik Meteomatics ızgarası")
            fields[name] = arr.reshape(shape) * scale
        out.update(fields)
        out.update({"live": True, "time": stamp})
        sources.insert(0, "Meteomatics")
    except Exception:
        pass
    out["source"] = " + ".join(sources) if sources else "simülasyon"
    return out

