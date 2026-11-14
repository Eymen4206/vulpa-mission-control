"""NASA POWER (Earthdata · MERRA-2): uzun vadeli sıcaklık ve yağış trendi (mevsimsel Mann-Kendall).

app.py içindeki fonksiyonların birebir kopyası; POWER'a ulaşılamazsa simülasyon serisine geçer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pymannkendall as mk
import requests
import streamlit as st

from .config import PERIOD, POWER_URL, WEATHER_TTL
from .regions import REGIONS, Region

def _power_simulated(spec: Region, y0: int, y1: int) -> pd.DataFrame:
    """POWER'a ulaşılamazsa: enlem ve mevsime dayalı, açıkça 'simülasyon' etiketli aylık seri."""
    dates = pd.date_range(f"{y0}-01-01", f"{y1}-12-01", freq="MS")
    rng = np.random.default_rng(spec.seed + 99)
    alat = abs(spec.lat)
    peak = 7 if spec.lat >= 0 else 1
    season = np.cos(2 * np.pi * (dates.month.to_numpy() - peak) / 12) * 10 * min(1.0, alat / 35)
    t = np.arange(len(dates)) / 12
    temp = 27 - 0.42 * alat + season + 0.025 * t + rng.normal(0, 0.6, len(dates))
    prec = np.maximum(0, 70 + 30 * np.cos(2 * np.pi * (dates.month.to_numpy() - peak) / 12)
                      + rng.normal(0, 20, len(dates)))
    return pd.DataFrame({"T2M": temp, "PREC": prec}, index=dates)


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _fetch_power(city: str, y0: int, y1: int) -> dict:
    """NASA POWER günlük nokta API'sinden y0–y1 T2M (°C) ve PRECTOTCORR (mm/gün) alır (tarih parametreleri seçili
    yıla göre dinamik), aylığa toplar ve mevsimsel Mann-Kendall + Sen eğilimiyle uzun vadeli trendi hesaplar."""
    spec = REGIONS[city]
    try:
        resp = requests.get(POWER_URL, params={
            "parameters": "T2M,PRECTOTCORR", "community": "AG", "format": "JSON",
            "latitude": round(spec.lat, 4), "longitude": round(spec.lon, 4),
            "start": f"{y0}0101", "end": f"{y1}1231",
        }, timeout=25)
        resp.raise_for_status()
        par = resp.json()["properties"]["parameter"]
        daily = pd.DataFrame({"T2M": pd.Series(par["T2M"]), "PREC": pd.Series(par["PRECTOTCORR"])})
        daily.index = pd.to_datetime(daily.index, format="%Y%m%d")
        daily = daily.where(daily > -900)
        monthly = daily.resample("MS").agg({"T2M": "mean", "PREC": "sum"})
        monthly["T2M"] = monthly["T2M"].interpolate(limit_direction="both")
        live = True
    except Exception:
        monthly, live = _power_simulated(spec, y0, y1), False
    t_res = mk.seasonal_test(monthly["T2M"].to_numpy(dtype=float), period=PERIOD)
    p_res = mk.seasonal_test(monthly["PREC"].to_numpy(dtype=float), period=PERIOD)
    annual = monthly.groupby(monthly.index.year).agg({"T2M": "mean", "PREC": "sum"})
    prec_mean = float(annual["PREC"].mean())
    return {
        "live": live,
        "live_src": live, "y0": y0, "y1": y1,
        "source": f"NASA POWER (MERRA-2) · {y0}–{y1}" if live else f"NASA POWER · {y0}–{y1} · simülasyon",
        "t_trend": t_res.trend, "t_p": float(t_res.p), "t_dec": float(t_res.slope) * 10,
        "p_trend": p_res.trend, "p_p": float(p_res.p), "p_dec": float(p_res.slope) * 12 * 10,  # mm/yıl/10 yıl
        "p_dec_pct": float(p_res.slope) * 12 * 10 / prec_mean * 100 if prec_mean > 0 else 0.0,
        "t_mean": float(annual["T2M"].mean()), "prec_mean": prec_mean,
        "years": [int(y) for y in annual.index], "annual_t": [round(float(v), 2) for v in annual["T2M"]],
        "warmest": int(annual["T2M"].idxmax()),
        "shift": float(annual["T2M"].iloc[-5:].mean() - annual["T2M"].iloc[:5].mean()),
        "last_t": float(annual["T2M"].iloc[-1]), "last_dev": float(annual["T2M"].iloc[-1] - annual["T2M"].mean()),
        "last_prec": float(annual["PREC"].iloc[-1]),
    }

