# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Sene ortalaması (yıllık ortalama) — Frontend'in "Sene Ortalaması" seçeneği için.

Kaynak: NASA POWER aylık uç noktası (MERRA-2). Her nokta için 1991–2025 yıllarının aylık değerleri ve hazır yıllık
ortalamaları ("YYYY13") tek istekte gelir. Tüm bölgeler ve 264 ızgara noktası `snapshots/annual.json` dosyasına bir kez
yazılır; uygulama bu dosyayı okur, ağ isteği ve kota harcamaz.

Değişkenler: T2M (°C), PS (kPa → deniz seviyesine indirgenmiş hPa), WS10M (m/s → km/sa), WD10M (°), RH2M (%).
Rüzgâr yönü aylık rüzgâr vektörlerinin ortalamasıdır (yalnızca açıların ortalaması alınmaz).
Sapma: yıllık ortalama sıcaklık − 1991–2020 ortalaması (Dünya Meteoroloji Örgütü standart normal dönemi).

Yenilemek için:  .venv\\Scripts\\python -m data_pipelines.refresh_annual
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
import streamlit as st

from .climatology import grid_normals, msl_from_ps, region_normals
from .config import GRID_LATS, GRID_LONS, LAST_FULL_YEAR, WEATHER_TTL
from .regions import REGION_LIST

ANNUAL_PATH = Path(__file__).with_name("snapshots") / "annual.json"
POWER_MONTHLY_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
FIRST_YEAR = 1991
BASELINE = (1991, 2020)


def fetch_annual_point(lat: float, lon: float, y0: int = FIRST_YEAR, y1: int = LAST_FULL_YEAR) -> dict:
    """Tek nokta için y0–y1 yıllık ortalamaları. 429'da istisna fırlatır (betik bekleyip yeniden dener).

    Dönüş: {"elev", "years": [..], "T2M": [..], "MSL": [..] (hPa), "WS": [..] (km/sa), "WD": [..] (°), "RH": [..] (%)}
    """
    resp = requests.get(POWER_MONTHLY_URL, params={
        "parameters": "T2M,PS,WS10M,WD10M,RH2M", "community": "AG", "format": "JSON",
        "latitude": round(lat, 4), "longitude": round(lon, 4), "start": y0, "end": y1,
    }, timeout=60)
    resp.raise_for_status()
    js = resp.json()
    par = js["properties"]["parameter"]
    elev = float(js["geometry"]["coordinates"][2])
    out = {"elev": round(elev, 1), "years": [], "T2M": [], "MSL": [], "WS": [], "WD": [], "RH": []}
    for y in range(y0, y1 + 1):
        ann = {k: par[k].get(f"{y}13") for k in ("T2M", "PS", "WS10M", "RH2M")}
        if any(v is None or v < -900 for v in ann.values()):
            continue
        # Rüzgâr yönü: aylık (hız, yön) vektörlerinin ortalaması. Meteorolojik yön = rüzgârın geldiği yön.
        u = v = 0.0
        for m in range(1, 13):
            ws, wd = par["WS10M"].get(f"{y}{m:02d}"), par["WD10M"].get(f"{y}{m:02d}")
            if ws is None or wd is None or ws < -900 or wd < -900:
                continue
            u += -ws * math.sin(math.radians(wd))
            v += -ws * math.cos(math.radians(wd))
        wd_mean = (math.degrees(math.atan2(-u, -v)) + 360) % 360
        out["years"].append(y)
        out["T2M"].append(round(ann["T2M"], 2))
        out["MSL"].append(msl_from_ps(ann["PS"] * 10, elev, ann["T2M"]))
        out["WS"].append(round(ann["WS10M"] * 3.6, 1))
        out["WD"].append(round(wd_mean, 1))
        out["RH"].append(round(ann["RH2M"], 1))
    if not out["years"]:
        raise ValueError("yıllık veri yok")
    return out


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def load_annual() -> dict:
    try:
        return json.loads(ANNUAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"regions": {}, "grid": []}


def _year_values(rec: dict, year: int) -> dict | None:
    """Kayıttan o yılın değerleri ve 1991–2020 sapması."""
    if not rec or year not in rec["years"]:
        return None
    i = rec["years"].index(year)
    base = [t for y, t in zip(rec["years"], rec["T2M"]) if BASELINE[0] <= y <= BASELINE[1]]
    anomaly = round(rec["T2M"][i] - float(np.mean(base)), 2) if len(base) >= 20 else None
    return {"temp": rec["T2M"][i], "pressure": rec["MSL"][i], "wind": rec["WS"][i], "wind_dir": rec["WD"][i],
            "humidity": rec["RH"][i], "anomaly": anomaly}


def _annual_normals_region(name: str) -> dict | None:
    """Yedek: aylık iklim normallerinin yıllık ortalaması (sapma bilinmez)."""
    n = region_normals(name)
    if n is None:
        return None
    return {"temp": round(float(np.mean(n["T2M"])), 1), "pressure": round(float(np.mean(n["MSL"])), 1),
            "wind": round(float(np.mean(n["WS10M"])) * 3.6, 1), "wind_dir": 270.0,
            "humidity": round(float(np.mean(n["RH2M"])), 1), "anomaly": None}


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_weather_annual(year: int) -> dict:
    """Tüm bölgelerin `year` yılı ortalaması; `_fetch_weather(year)` ile aynı şema.

    Ek alanlar: "annual": True, "date": "YYYY", "anomaly_kind": "annual" (1991–2020 normaline göre yıllık sapma).
    Yıl kayıtta yoksa (ör. içinde bulunulan yıl) iklim normallerinin yıllık ortalaması `live=False` ile döner.
    İstisna fırlatmaz.
    """
    year = int(year)
    regions = load_annual().get("regions", {})
    data, real = {}, 0
    for r in REGION_LIST:
        vals = _year_values(regions.get(r.name), year)
        if vals is not None:
            real += 1
        else:
            vals = _annual_normals_region(r.name) or {"temp": 15.0, "pressure": 1013.0, "wind": 15.0,
                                                      "wind_dir": 270.0, "humidity": None, "anomaly": None}
        data[r.name] = {**vals, "label": "Sene ortalaması", "label_en": "Year average", "icon": "📅"}
    live = real == len(REGION_LIST)
    if live:
        source = f"NASA POWER (MERRA-2) · {year} sene ortalaması · sapma: {BASELINE[0]}–{BASELINE[1]} normaline göre"
        source_en = (f"NASA POWER (MERRA-2) · {year} year average · anomaly vs the {BASELINE[0]}–{BASELINE[1]} "
                     "normal")
    else:
        source = f"{year} sene ortalaması henüz yok · NASA POWER iklim normali (tahmini)"
        source_en = f"No {year} year average yet · NASA POWER climate normal (estimated)"
    return {"live": live, "time": str(year), "data": data, "year": year, "month": None, "day": None,
            "date": str(year), "annual": True, "provider": "NASA POWER" if live else "İklim normali",
            "source": source, "source_en": source_en, "anomaly_live": live,
            "anomaly_kind": "annual" if live else None}


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_grid_annual(year: int) -> dict:
    """15° ızgaranın `year` yılı ortalaması (numpy 11 × 24); `_fetch_grid(year)` ile aynı şema.
    Ek alanlar: "annual": True, "date": "YYYY", "anomaly_kind": "annual". İstisna fırlatmaz."""
    year = int(year)
    pts = load_annual().get("grid", [])
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    vals = [_year_values(p, year) for p in pts] if len(pts) == la.size else []
    out = {"time": str(year), "year": year, "month": None, "day": None, "date": str(year), "annual": True}
    if vals and all(v is not None for v in vals):
        for key, name in (("temp", "temp"), ("pressure", "pressure"), ("wind", "wind"), ("wind_dir", "wind_dir")):
            out[name] = np.array([v[key] for v in vals], dtype=float).reshape(la.shape)
        out["anomaly"] = np.array([0.0 if v["anomaly"] is None else v["anomaly"] for v in vals],
                                  dtype=float).reshape(la.shape)
        out.update({"live": True, "anomaly_live": True, "anomaly_kind": "annual",
                    "source": f"NASA POWER (MERRA-2) · {year} sene ortalaması",
                    "source_en": f"NASA POWER (MERRA-2) · {year} year average"})
        return out
    # Yedek: aylık normallerin yıllık ortalaması
    months = [grid_normals(datetime(2001, m, 15, 12, tzinfo=timezone.utc)) for m in range(1, 13)]
    if all(m is not None for m in months):
        for k in ("temp", "pressure", "wind"):
            out[k] = np.round(np.mean([m[k] for m in months], axis=0), 1)
    else:
        alat = np.abs(la)
        out.update({"temp": 27 - 0.45 * alat, "pressure": np.full_like(la, 1013.0), "wind": np.full_like(la, 15.0)})
    alat = np.abs(la)
    out.update({"wind_dir": np.where(alat < 30, 90.0, np.where(alat < 60, 270.0, 90.0)),
                "anomaly": np.zeros_like(la), "live": False, "anomaly_live": False, "anomaly_kind": None,
                "source": f"{year} sene ortalaması henüz yok · NASA POWER iklim normali (tahmini)",
                "source_en": f"No {year} year average yet · NASA POWER climate normal (estimated)"})
    return out


def write_annual(regions: dict, grid: list) -> Path:
    ANNUAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "source": "NASA POWER monthly (MERRA-2) — yıllık ortalamalar", "baseline": list(BASELINE),
               "units": {"T2M": "°C", "MSL": "hPa", "WS": "km/sa", "WD": "° (vektör ortalaması)", "RH": "%"},
               "regions": regions, "grid": grid}
    ANNUAL_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return ANNUAL_PATH


def fetch_with_retry(lat: float, lon: float, tries: int = 6) -> dict | None:
    """Betik için: 429 / ağ hatasında artan bekleme ile yeniden dener."""
    for attempt in range(tries):
        try:
            return fetch_annual_point(lat, lon)
        except requests.HTTPError as exc:
            wait = 20 * (attempt + 1) if exc.response is not None and exc.response.status_code == 429 else 3
            time.sleep(wait)
        except Exception:
            time.sleep(3)
    return None


# ── Yıl aralığı: iki yılın SENE ORTALAMASI farkı (15.11.2026) ─────────────────────────────────────────────────────
# "2015 ile 2024 arasındaki fark" sorusu tek bir günün (12:00 UTC) havasıyla yanıtlanırsa günlük hava gürültüsü baskın
# olur. Sene ortalamaları annual.json'da hazır: ağ isteği yok, kota yok, anında döner. Şema `_fetch_weather_range` ile
# aynıdır (`*_start`, `*_delta`, `delta_summary`, `range`, `delta_live`); ek alan: "annual": True.
def _fetch_weather_annual_range(start_year: int, end_year: int) -> dict:
    from .weather import DELTA_FIELDS, _delta
    sy, ey = sorted((int(start_year), int(end_year)))
    s, e = _fetch_weather_annual(sy), _fetch_weather_annual(ey)
    data, deltas = {}, {f: {} for f in DELTA_FIELDS}
    for name, w_end in e["data"].items():
        w = dict(w_end)
        w_start = s["data"].get(name, {})
        for f in DELTA_FIELDS:
            w[f"{f}_start"] = w_start.get(f)
            w[f"{f}_delta"] = _delta(w_start.get(f), w_end.get(f))
            if w[f"{f}_delta"] is not None:
                deltas[f][name] = w[f"{f}_delta"]
        data[name] = w
    summary = {}
    for f, vals in deltas.items():
        if vals:
            summary[f] = {"mean": round(float(np.mean(list(vals.values()))), 2),
                          "max_region": max(vals, key=vals.get), "max": max(vals.values()),
                          "min_region": min(vals, key=vals.get), "min": min(vals.values()),
                          "up": sum(1 for v in vals.values() if v > 0), "n": len(vals)}
    both = bool(s["live"] and e["live"])
    est = "" if both else " · bir uç iklim normali (tahmini)"
    est_en = "" if both else " · one end is the climate normal (estimated)"
    return {**e, "data": data, "range": True, "annual": True, "year": ey, "start_year": sy, "end_year": ey,
            "start_time": str(sy), "end_time": str(ey), "start_live": s["live"], "end_live": e["live"],
            "delta_live": both, "delta_summary": summary, "date": f"{sy}–{ey}",
            "source": f"NASA POWER (MERRA-2) · {sy} → {ey} sene ortalaması farkı{est}",
            "source_en": f"NASA POWER (MERRA-2) · {sy} → {ey} year-average difference{est_en}"}


def _fetch_grid_annual_range(start_year: int, end_year: int) -> dict:
    """15° ızgarada iki yılın sene ortalaması farkı: `temp_delta`, `pressure_delta`, `wind_delta` (numpy 11 × 24) ve
    `*_start`. Şema `grid._fetch_grid_range` ile aynı; ağ isteği yok."""
    sy, ey = sorted((int(start_year), int(end_year)))
    s, e = _fetch_grid_annual(sy), _fetch_grid_annual(ey)
    out = dict(e)
    for f in ("temp", "pressure", "wind"):
        out[f"{f}_start"] = s[f]
        out[f"{f}_delta"] = np.round(np.asarray(e[f], dtype=float) - np.asarray(s[f], dtype=float), 2)
    both = bool(s["live"] and e["live"])
    out.update({"range": True, "annual": True, "start_year": sy, "end_year": ey, "start_time": str(sy),
                "end_time": str(ey), "start_live": s["live"], "end_live": e["live"], "delta_live": both,
                "date": f"{sy}–{ey}",
                "source": f"NASA POWER (MERRA-2) · {sy} → {ey} sene ortalaması farkı" + ("" if both else " · tahmini"),
                "source_en": f"NASA POWER (MERRA-2) · {sy} → {ey} year-average difference" + ("" if both else
                                                                                            " · estimated")})
    return out
