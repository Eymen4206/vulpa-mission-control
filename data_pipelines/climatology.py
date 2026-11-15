# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""İklim normalleri (NASA POWER climatology) — gerçekçi yedek değerler ve "iklim normaline göre sapma".

Neden: Kaynaklar (Meteomatics / Open-Meteo) düştüğünde eskiden enlem formülüyle üretilen simülasyon, ay normalinden
ortalama 5,9 °C, en fazla 26,6 °C sapıyordu (ör. Grönland'da Kasım'da −7,7 °C; gerçek normal −34 °C). Artık
yedek değerler her bölge/ızgara noktası ve her ay için NASA POWER'ın uzun dönem ortalamalarından gelir:

    T2M (aylık ortalama sıcaklık), T2M_RANGE (ortalama günlük sıcaklık farkı), WS10M (10 m rüzgâr, m/s),
    RH2M (bağıl nem, %), PS (yüzey basıncı, kPa → deniz seviyesine indirgenir).

Gün içi döngü: beklenen sıcaklık = T2M + (T2M_RANGE / 2) · cos(2π · (yerel güneş saati − 15) / 24).
En yüksek değer yerel saat 15:00'te, en düşük 03:00'te varsayılır.

Veri depodaki `snapshots/climatology.json` dosyasından okunur (tüm bölgeler + 264 ızgara noktası); ağ isteği yapılmaz.
Yenilemek için: `.venv\\Scripts\\python -m data_pipelines.refresh_climatology`
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
import streamlit as st

from .config import GRID_LATS, GRID_LONS, WEATHER_TTL

CLIM_PATH = Path(__file__).with_name("snapshots") / "climatology.json"
CLIM_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
FIELDS = ("T2M", "T2M_RANGE", "WS10M", "RH2M", "PS")


def msl_from_ps(ps_hpa: float, elev_m: float, t2m_c: float) -> float:
    """Yüzey basıncını deniz seviyesine indirger (hipsometrik denklem, sütun ortalama sıcaklığıyla).

    Sütun sıcaklığı = yüzey sıcaklığı + 0,0065 K/m · z / 2 (standart sıcaklık düşüş oranı). Soğuk ve yüksek buz
    platolarında (Grönland, Antarktika, Tibet) indirgeme fiziksel olarak belirsizdir ve aşırı değer üretir; bu
    yüzden sonuç 960–1050 hPa aralığına sınırlanır (yalnızca yedek gösterim içindir)."""
    t_col = t2m_c + 273.15 + 0.00325 * elev_m
    msl = ps_hpa * math.exp(elev_m / (29.27 * t_col))
    return round(min(max(msl, 960.0), 1050.0), 1)


def fetch_point(lat: float, lon: float) -> dict:
    """Tek nokta için 12 aylık normaller. Dönüş: {"elev": m, "T2M": [12], "T2M_RANGE": [12], "WS10M": [12],
    "RH2M": [12], "MSL": [12] (hPa)}. Ağ hatasında istisna fırlatır (betik kullanır)."""
    resp = requests.get(CLIM_URL, params={"parameters": ",".join(FIELDS), "community": "AG", "format": "JSON",
                                          "latitude": round(lat, 4), "longitude": round(lon, 4)}, timeout=60)
    resp.raise_for_status()
    js = resp.json()
    par = js["properties"]["parameter"]
    elev = float(js["geometry"]["coordinates"][2])
    out = {"elev": round(elev, 1)}
    for f in ("T2M", "T2M_RANGE", "WS10M", "RH2M"):
        out[f] = [round(float(par[f][m]), 2) for m in MONTHS]
    out["MSL"] = [msl_from_ps(float(par["PS"][m]) * 10, elev, out["T2M"][i]) for i, m in enumerate(MONTHS)]
    if any(v is None or v < -900 for f in ("T2M", "T2M_RANGE", "WS10M", "RH2M") for v in out[f]):
        raise ValueError("eksik normal")
    return out


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def load_climatology() -> dict:
    """{"regions": {ad: nokta}, "grid": [264 nokta, GRID sırasıyla], "generated": ...} ya da boş."""
    try:
        return json.loads(CLIM_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"regions": {}, "grid": []}


def region_normals(name: str) -> dict | None:
    return load_climatology().get("regions", {}).get(name)


def expected_temp(normals: dict, lon: float, when: datetime) -> float:
    """O anda (UTC) beklenen sıcaklık: aylık ortalama + gün içi döngü (yerel güneş saatine göre)."""
    i = when.month - 1
    local_hour = (when.hour + when.minute / 60 + lon / 15.0) % 24
    return normals["T2M"][i] + normals["T2M_RANGE"][i] / 2 * math.cos(2 * math.pi * (local_hour - 15) / 24)


def normal_values(normals: dict, lon: float, when: datetime) -> dict:
    """Yedek gösterim için o ana ait normal değerler (sıcaklık °C, basınç hPa, rüzgâr km/sa, nem %)."""
    i = when.month - 1
    return {"temp": round(expected_temp(normals, lon, when), 1), "pressure": normals["MSL"][i],
            "wind": round(normals["WS10M"][i] * 3.6, 1), "humidity": normals["RH2M"][i]}


def grid_normals(when: datetime) -> dict | None:
    """264 ızgara noktası için o ana ait normal alanlar (11 × 24) ya da veri yoksa None."""
    pts = load_climatology().get("grid", [])
    if len(pts) != len(GRID_LATS) * len(GRID_LONS):
        return None
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    vals = [normal_values(p, float(x), when) for p, x in zip(pts, lo.ravel())]
    return {k: np.array([v[k] for v in vals], dtype=float).reshape(la.shape)
            for k in ("temp", "pressure", "wind", "humidity")}


def climatology_anomaly(name: str, lon: float, temp: float | None, when: datetime) -> float | None:
    """İklim normaline göre sapma: ölçülen sıcaklık − o saat ve ay için beklenen sıcaklık (°C)."""
    n = region_normals(name)
    if n is None or temp is None:
        return None
    return round(float(temp) - expected_temp(n, lon, when), 2)


def grid_climatology_anomaly(temp: np.ndarray, when: datetime) -> np.ndarray | None:
    norm = grid_normals(when)
    if norm is None:
        return None
    return np.round(np.asarray(temp, dtype=float) - norm["temp"], 2)


def write_climatology(regions: dict, grid: list) -> Path:
    CLIM_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "source": "NASA POWER climatology (MERRA-2 uzun dönem ortalaması)",
               "fields": {"T2M": "°C", "T2M_RANGE": "°C (ortalama günlük fark)", "WS10M": "m/s", "RH2M": "%",
                          "MSL": "hPa (yüzey basıncından indirgenmiş)", "elev": "m"},
               "regions": regions, "grid": grid}
    CLIM_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return CLIM_PATH
