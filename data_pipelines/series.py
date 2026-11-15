# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Bölge tema serileri (gerçek veri, yoksa sentetik) ve mevsimsel Mann-Kendall analizi."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pymannkendall as mk
import streamlit as st

from .config import END, PERIOD, PROJECTION_MONTHS, START, WEATHER_TTL
from .real_series import real_series
from .regions import REGIONS


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def build_series(region_name: str) -> pd.DataFrame:
    """Bölgenin aylık tema serisi (START–END). Dönüş yapısı değişmedi: {"Tarih", <spec.variable>}.

    Önce gerçek veri (real_series: anlık görüntü → canlı istek), alınamazsa tekrarlanabilir sentetik seri.
    Hangisinin kullanıldığını `series_meta(region_name)` söyler.
    """
    rec = real_series(region_name)
    if rec is not None:
        spec = REGIONS[region_name]
        return pd.DataFrame({"Tarih": pd.date_range(START, END, freq="MS"),
                             spec.variable: np.asarray(rec["values"], dtype=float)})
    return synthetic_series(region_name)


def synthetic_series(region_name: str) -> pd.DataFrame:
    """Bölgeye özgü, tekrarlanabilir sentetik aylık seri (gerçek veri olmayan bölgeler ve yedek için)."""
    spec = REGIONS[region_name]
    dates = pd.date_range(START, END, freq="MS")
    n = len(dates)
    rng = np.random.default_rng(spec.seed)
    t = np.arange(n, dtype=float)
    month = dates.month.to_numpy()
    seasonal = spec.season_amp * np.cos(2 * np.pi * (month - spec.peak_month) / 12.0)
    trend = (spec.trend_per_year / 12.0) * t

    # AR(1) otokorelasyonlu gürültü
    shock = rng.normal(0.0, spec.noise, size=n)
    noise = np.empty(n, dtype=float)
    noise[0] = shock[0]
    for i in range(1, n):
        noise[i] = spec.ar * noise[i - 1] + shock[i]

    values = spec.base + seasonal + trend + noise
    if spec.floor is not None:
        values = np.maximum(values, spec.floor)
    return pd.DataFrame({"Tarih": dates, spec.variable: values})


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def analyze(region_name: str) -> dict:
    """Mevsimsel Mann-Kendall testi (periyot = 12) ve yardımcı tanı istatistikleri."""
    spec = REGIONS[region_name]
    values = build_series(region_name)[spec.variable].to_numpy(dtype=float)
    n = len(values)
    res = mk.seasonal_test(values, period=PERIOD)
    # seasonal_test eğimi dönem (yıl) başına verir; doğru: intercept + slope · t / period
    slope_m = float(res.slope) / PERIOD

    half = n // 2
    h1 = mk.seasonal_test(values[:half], period=PERIOD)
    h2 = mk.seasonal_test(values[half:], period=PERIOD)

    months = np.arange(n) % PERIOD
    detrended = values - (float(res.intercept) + slope_m * np.arange(n))
    clim = np.array([detrended[months == m].mean() for m in range(PERIOD)])
    resid = detrended - clim[months]

    first = values[:60].reshape(-1, PERIOD).mean(axis=0)
    last = values[-60:].reshape(-1, PERIOD).mean(axis=0)
    return {
        "trend": res.trend, "p": float(res.p), "z": float(res.z), "Tau": float(res.Tau), "s": float(res.s),
        "slope": slope_m, "slope_year": float(res.slope), "intercept": float(res.intercept), "n": n,
        "s1": float(h1.slope), "s2": float(h2.slope), "p1": float(h1.p), "p2": float(h2.p),
        "resid_std": float(resid.std(ddof=1)),
        "rho1": float(np.corrcoef(resid[:-1], resid[1:])[0, 1]),
        "amp_first": float(first.max() - first.min()), "amp_last": float(last.max() - last.min()),
        "peak_month": int(np.argmax(last)) + 1,
        "projection": float(res.intercept) + slope_m * (n - 1 + PROJECTION_MONTHS),
    }

