"""15°'lik küresel meteoroloji ızgarası (11 × 24) — termal alan, izobarlar ve rüzgâr vektörleri için ham veri.

app.py içindeki fonksiyonların birebir kopyası. Görselleştirme katmanı (grid_layers, _resample,
_contour_segments, renk durakları) app.py'de kalır.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import streamlit as st

from .climatology import grid_climatology_anomaly, grid_normals
from .config import GRID_LATS, GRID_LONS, GRID_STEP, MM_CORE, WEATHER_TTL, hist_date
from .weather import (
    DELTA_FIELDS, DataUnavailable, _om_get, anomaly_for, disk_load, disk_save, meteomatics_now, mm_hist,
    om_archive_instant, run_parallel,
    range_source, range_year,
)

def _fallback_grid(when: datetime | None = None) -> dict:
    """Ağ yoksa: NASA POWER iklim normalleri (264 nokta, o ay ve saat), yoksa kuşaksal tahmini alanlar.
    Her iki durumda da 'live': False döner; arayüz 'tahmini' etiketi göstermelidir."""
    when = when or datetime.now(timezone.utc)
    norm = grid_normals(when)
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    if norm is not None:
        alat = np.abs(la)
        return {"live": False, "time": when.strftime("%H:%M"), "source": "NASA POWER iklim normali (tahmini)",
                "temp": norm["temp"], "anomaly": np.zeros_like(la), "pressure": norm["pressure"],
                "wind": norm["wind"], "wind_dir": np.where(alat < 30, 90.0, np.where(alat < 60, 270.0, 90.0)),
                "anomaly_live": False, "anomaly_kind": None}
    alat = np.abs(la)
    pressure = 1010 + 10 * np.exp(-((alat - 30) / 10) ** 2) - 12 * np.exp(-((alat - 60) / 8) ** 2) \
        + 3 * np.cos(np.radians(lo * 3))
    wind_dir = np.where(alat < 30, 90.0, np.where(alat < 60, 270.0, 90.0))
    return {"live": False, "time": datetime.now(timezone.utc).strftime("%H:%M"), "source": "simülasyon",
            "temp": 27 - 0.45 * alat, "anomaly": np.zeros_like(la), "pressure": pressure,
            "wind": np.full_like(la, 15.0), "wind_dir": wind_dir}


def _grid_points() -> tuple[np.ndarray, np.ndarray, list[tuple[float, float]], str]:
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    box = (f"{GRID_LATS[-1]:g},{GRID_LONS[0]:g}_{GRID_LATS[0]:g},{GRID_LONS[-1]:g}:"
           f"{GRID_STEP:g},{GRID_STEP:g}")
    keys = [(float(a), float(b)) for a, b in zip(la.ravel(), lo.ravel())]
    return la, lo, keys, box


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _hist_grid_instant(year: int, month: int | None, day: int | None) -> tuple[dict, str]:
    """Seçilen andaki ızgara alanları: Meteomatics ızgara sorgusu (tek istek, 8 sn sınır) → Open-Meteo ERA5 (264 nokta).
    Başarısızlık önbelleğe yazılmaz (DataUnavailable)."""
    when = hist_date(year, month, day)
    la, lo, keys, box = _grid_points()
    cached = disk_load("grid", when)
    if cached:
        return {k: np.array(v, dtype=float) for k, v in cached["fields"].items()}, cached["provider"]
    try:
        mm = mm_hist(MM_CORE, box, when, timeout=8)
        fields = {}
        for param, name, scale in (("t_2m:C", "temp", 1.0), ("msl_pressure:hPa", "pressure", 1.0),
                                   ("wind_speed_10m:ms", "wind", 3.6), ("wind_dir_10m:d", "wind_dir", 1.0)):
            arr = np.array([mm[param].get(k) for k in keys], dtype=float)
            if np.isnan(arr).any():
                raise ValueError("eksik Meteomatics ızgarası")
            fields[name] = arr.reshape(la.shape) * scale
        disk_save("grid", when, {"fields": {k: v.tolist() for k, v in fields.items()}, "provider": "Meteomatics"})
        return fields, "Meteomatics"
    except Exception:
        pass
    try:
        om = om_archive_instant(la.ravel(), lo.ravel(), when, timeout=25)
        fields = {name: np.array([r[src] for r in om], dtype=float).reshape(la.shape)
                  for name, src in (("temp", "temperature_2m"), ("pressure", "pressure_msl"),
                                    ("wind", "wind_speed_10m"), ("wind_dir", "wind_direction_10m"))}
        if any(np.isnan(v).any() for v in fields.values()):
            raise ValueError("eksik arşiv ızgarası")
        disk_save("grid", when, {"fields": {k: v.tolist() for k, v in fields.items()}, "provider": "Open-Meteo ERA5"})
        return fields, "Open-Meteo ERA5"
    except Exception as exc:
        raise DataUnavailable(str(exc)) from exc


# Termal sapma için kaba ızgara (30°, 6 × 12 = 72 nokta): Open-Meteo dakikalık kotasını korur (264 yerine 72 konum,
# 31 günlük seri). Sonuç 15° ızgaraya (11 × 24) doğrusal ara değerlenir; sapma alanı zaten yumuşak bir alandır.
COARSE_LATS = np.arange(-75, 76, 30, dtype=float)
COARSE_LONS = np.arange(-180, 180, 30, dtype=float)


def _coarse_to_grid(coarse: np.ndarray) -> np.ndarray:
    """30° alanı 15° ızgaraya taşır: boylamda periyodik, enlemde doğrusal ara değerleme."""
    lons_ext = np.append(COARSE_LONS, 180.0)
    rows = np.array([np.interp(GRID_LONS, lons_ext, np.append(r, r[0])) for r in coarse])   # 6 × 24
    return np.array([np.interp(GRID_LATS, COARSE_LATS, rows[:, j]) for j in range(rows.shape[1])]).T


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _hist_grid_anomaly(year: int, month: int | None, day: int | None) -> tuple[np.ndarray, str]:
    when = hist_date(year, month, day)
    cached = disk_load("grid_anom", when)
    if cached:
        return np.array(cached["values"], dtype=float), cached["source"]
    cla, clo = np.meshgrid(COARSE_LATS, COARSE_LONS, indexing="ij")
    box = f"{COARSE_LATS[-1]:g},{COARSE_LONS[0]:g}_{COARSE_LATS[0]:g},{COARSE_LONS[-1]:g}:30,30"
    vals, src = anomaly_for(cla.ravel(), clo.ravel(), box, when)
    coarse = np.array([np.nan if v is None else v for v in vals], dtype=float).reshape(cla.shape)
    coarse = np.where(np.isnan(coarse), np.nanmean(coarse), coarse)
    grid = np.round(_coarse_to_grid(coarse), 3)
    disk_save("grid_anom", when, {"values": grid.tolist(), "source": src})
    return grid, src


def _fetch_historical_grid(year: int, month: int | None = None, day: int | None = None,
                           anomaly: bool = True) -> dict:
    """Seçilen tarih (varsayılan: o yılda bugünün takvim günü) için küresel ızgara.

    Anlık alanlar Meteomatics'ten, olmazsa Open-Meteo ERA5 arşivinden; termal sapma (30° ızgarada hesaplanıp 15°'ye
    ara değerlenir) önce Open-Meteo arşivinden, olmazsa Meteomatics'ten. Hepsi başarısızsa simülasyon; önbelleğe yazılmaz, RETRY_AFTER sn sonra yeniden denenir.
    """
    when = hist_date(year, month, day)
    out = _fallback_grid(when)
    out.update({"time": when.strftime("%d.%m.%Y %H:%M"), "year": year, "month": when.month, "day": when.day,
                "date": when.strftime("%Y-%m-%d"), "anomaly_live": False})
    jobs = [(("g-inst", year, month, day), _hist_grid_instant, (year, month, day))]
    if anomaly:   # aralık modunun başlangıç ucunda sapma kullanılmaz: Open-Meteo kotası harcanmaz
        jobs.append((("g-anom", year, month, day), _hist_grid_anomaly, (year, month, day)))
    inst, anom = (run_parallel(*jobs) + [None])[:2]
    if inst is None:
        return out
    fields, provider = inst
    out.update(fields)
    out.update({"live": True, "source": provider})
    if anom is not None:
        out["anomaly"], src = anom
        out.update({"anomaly_live": True, "anomaly_kind": "30d"})
        if src != provider:
            out["source"] = f"{provider} · sapma: {src}"
    else:
        clim = grid_climatology_anomaly(out["temp"], when)
        if clim is not None:
            out.update({"anomaly": clim, "anomaly_live": True, "anomaly_kind": "climatology",
                        "source": f"{provider} · sapma: iklim normaline göre (NASA POWER)"})
        else:
            out["source"] = f"{provider} · sapma alınamadı"
    return out


def _fetch_grid(start_year: int = 0, end_year: int | None = None, month: int | None = None,
                day: int | None = None) -> dict:
    """15° küresel ızgara.

    - Tek yıl (geriye uyumlu): `_fetch_grid(year)` → 0 canlı, aksi halde o yılın bugünkü takvim günü.
    - Yıl aralığı: `_fetch_grid(start_year, end_year)` → bitiş yılının alanları + `temp_delta`,
      `pressure_delta`, `wind_delta` (bitiş − başlangıç, numpy 11×24).
    """
    if end_year is None:
        out = _fetch_historical_grid(start_year, month, day) if start_year else _fetch_live_grid()
    elif not month:   # 15.11.2026: ay yoksa sene ortalaması farkı (annual.json, ağ isteği yok)
        from .annual import _fetch_grid_annual_range
        out = _fetch_grid_annual_range(range_year(start_year), range_year(end_year))
    else:
        out = _fetch_grid_range(int(start_year), int(end_year), month, day)
    from .weather import with_source_en
    return with_source_en(out)


def _provider(s: dict, e: dict) -> str:
    """Aralık uçlarında gerçekte kullanılan kaynak ("Meteomatics", "Open-Meteo ERA5" ya da ikisi)."""
    pa, pb = (str(x.get("source", "")).split(" · ")[0] for x in (s, e))
    return pb if pa in ("", pb) else f"{pa} / {pb}"


def _fetch_grid_range(start_year: int, end_year: int, month: int | None = None, day: int | None = None) -> dict:
    """İki yılın aynı takvim günü için ızgara alanları ve farkları. İstisna fırlatmaz; uçlardan biri
    simülasyonsa `delta_live` False olur."""
    sy, ey = range_year(start_year), range_year(end_year)
    s = _fetch_historical_grid(sy, month, day, anomaly=False)   # başlangıcın sapması kullanılmaz (kota)
    e = _fetch_historical_grid(ey, month, day)
    out = dict(e)
    for f in DELTA_FIELDS:
        out[f"{f}_start"] = s[f]
        out[f"{f}_delta"] = np.round(np.asarray(e[f], dtype=float) - np.asarray(s[f], dtype=float), 2)
    both = s["live"] and e["live"]
    out.update({"range": True, "start_year": sy, "end_year": ey, "start_time": s["time"], "end_time": e["time"],
                "start_live": s["live"], "end_live": e["live"], "delta_live": both,
                "source": range_source(_provider(s, e), s, e)})
    return out


OM_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_live_grid() -> dict:
    """15°'lik küresel ızgara (264 nokta), canlı.

    - Anlık alanlar: Meteomatics ızgara sorgusu (tek istek); olmazsa Open-Meteo yalnızca "current" (264 konum).
    - Termal sapma: Open-Meteo'dan 30° kaba ızgarada (72 konum, son 30 gün) hesaplanıp 15°'ye ara değerlenir.
      Eski sürüm 264 konum × 31 gün istiyordu ve ücretsiz kotanın büyük kısmını tek başına tüketiyordu.
    Hiçbiri olmazsa kuşaksal simülasyon. 30 dk önbellek.
    """
    la, lo, keys, box = _grid_points()
    out = _fallback_grid()
    sources = []
    try:
        mm, stamp = meteomatics_now(MM_CORE, box, timeout=20)
        for param, name, scale in (("t_2m:C", "temp", 1.0), ("msl_pressure:hPa", "pressure", 1.0),
                                   ("wind_speed_10m:ms", "wind", 3.6), ("wind_dir_10m:d", "wind_dir", 1.0)):
            arr = np.array([mm[param].get(k) for k in keys], dtype=float)
            if np.isnan(arr).any():
                raise ValueError("eksik Meteomatics ızgarası")
            out[name] = arr.reshape(la.shape) * scale
        out.update({"live": True, "time": stamp})
        sources.append("Meteomatics")
    except Exception:
        try:
            items = _om_get({"latitude": ",".join(f"{v:g}" for v in la.ravel()),
                             "longitude": ",".join(f"{v:g}" for v in lo.ravel()),
                             "current": "temperature_2m,pressure_msl,wind_speed_10m,wind_direction_10m",
                             "timezone": "UTC"}, 20, url=OM_FORECAST_URL, name="open-meteo-forecast")
            if len(items) != la.size:
                raise ValueError("eksik ızgara yanıtı")
            for name, src in (("temp", "temperature_2m"), ("pressure", "pressure_msl"),
                              ("wind", "wind_speed_10m"), ("wind_dir", "wind_direction_10m")):
                out[name] = np.array([it["current"][src] or 0.0 for it in items], dtype=float).reshape(la.shape)
            out.update({"live": True, "time": items[0]["current"]["time"][-5:]})
            sources.append("Open-Meteo")
        except Exception:
            pass
    try:
        cla, clo = np.meshgrid(COARSE_LATS, COARSE_LONS, indexing="ij")
        items = _om_get({"latitude": ",".join(f"{v:g}" for v in cla.ravel()),
                         "longitude": ",".join(f"{v:g}" for v in clo.ravel()),
                         "daily": "temperature_2m_mean", "past_days": 30, "forecast_days": 1, "timezone": "UTC"},
                        20, url=OM_FORECAST_URL, name="open-meteo-forecast")
        vals = []
        for it in items:
            means = [v for v in it["daily"]["temperature_2m_mean"] if v is not None]
            vals.append(means[-1] - float(np.mean(means[:-1])) if len(means) >= 8 else np.nan)
        coarse = np.array(vals, dtype=float).reshape(cla.shape)
        if np.isnan(coarse).all():
            raise ValueError("sapma hesaplanamadı")
        coarse = np.where(np.isnan(coarse), np.nanmean(coarse), coarse)
        out["anomaly"] = np.round(_coarse_to_grid(coarse), 3)
        out.update({"anomaly_live": True, "anomaly_kind": "30d"})
        if "Open-Meteo" not in sources:
            sources.append("Open-Meteo (sapma)")
    except Exception:
        clim = grid_climatology_anomaly(out["temp"], datetime.now(timezone.utc)) if out.get("live") else None
        if clim is not None:
            out.update({"anomaly": clim, "anomaly_live": True, "anomaly_kind": "climatology"})
            sources.append("sapma: iklim normali (NASA POWER)")
        else:
            out.update({"anomaly_live": False, "anomaly_kind": None})
    out["source"] = " + ".join(sources) if sources else "simülasyon"
    return out
