"""Trend haritası (Büyük Plan, Aşama B · madde 3): "nerede artıyor, nerede azalıyor".

15° küresel ızgaranın (264 nokta) her noktasında seçilen değişkenin yıllık ortalamaları üzerinde Mann-Kendall + Sen.
Veri `snapshots/trendgrid.json` dosyasından okunur (NASA POWER aylık uç noktasının yıllık değerleri, 2001–son yıl,
15 değişken). Dosya yoksa sıcaklık için `annual.json` (1991–son yıl) kullanılır. Uygulama ağ isteği yapmaz.
Yenilemek için:  .venv\\Scripts\\python -m data_pipelines.refresh_trendgrid
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pymannkendall as mk
import streamlit as st

from .config import ALPHA, GRID_LATS, GRID_LONS, WEATHER_TTL
from .variables import VARIABLES, _DAYS

TRENDGRID_PATH = Path(__file__).with_name("snapshots") / "trendgrid.json"
MAP_KEYS = ("T2M", "PRECTOTCORR", "GWETROOT", "EVLAND", "AOD_55", "CLOUD_AMT", "ALLSKY_SFC_SW_DWN", "RH2M", "TS",
            "SNODP")


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def load_trendgrid() -> dict:
    try:
        return json.loads(TRENDGRID_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_trendgrid(points: list, y0: int, y1: int) -> Path:
    TRENDGRID_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "source": "NASA POWER monthly (MERRA-2) — yıllık değerler (YYYY13)", "years": [y0, y1],
               "grid": {"lats": list(GRID_LATS), "lons": list(GRID_LONS)}, "points": points}
    TRENDGRID_PATH.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return TRENDGRID_PATH


def annual_from_raw(params: dict, y0: int, y1: int) -> dict:
    """POWER ham yanıtından her değişkenin yıllık değeri (birim variables.py ile aynı; mm/gün → ortalama mm/ay)."""
    out = {}
    for key, v in VARIABLES.items():
        par = params.get(v[0], {})
        vals = []
        for y in range(y0, y1 + 1):
            x = par.get(f"{y}13")
            if x is None or x < -900:
                vals.append(None)
            else:
                vals.append(round(x * sum(_DAYS) / 12, 3) if v[3] == "mm_month" else round(float(x), 4))
        out[key] = vals
    return out


def _series_for(key: str) -> tuple[list | None, list[int] | None, str]:
    snap = load_trendgrid()
    pts = snap.get("points") or []
    if len(pts) == len(GRID_LATS) * len(GRID_LONS) and all(p and key in p for p in pts):
        y0, y1 = snap["years"]
        return [p[key] for p in pts], list(range(y0, y1 + 1)), f"NASA POWER (MERRA-2) · {y0}–{y1}"
    if key == "T2M":                                   # yedek: annual.json (1991–son yıl)
        from .annual import load_annual
        grid = load_annual().get("grid", [])
        if len(grid) == len(GRID_LATS) * len(GRID_LONS) and all(grid):
            years = grid[0]["years"]
            return [g["T2M"] for g in grid], years, f"NASA POWER (MERRA-2) · {years[0]}–{years[-1]}"
    return None, None, ""


def map_keys_available() -> list[str]:
    """Trend haritasında şu an seçilebilen değişkenler (anlık görüntüde olanlar)."""
    return [k for k in MAP_KEYS if _series_for(k)[0] is not None]


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _trend_map(key: str) -> dict | None:
    series, years, source = _series_for(key)
    if series is None:
        return None
    shape = (len(GRID_LATS), len(GRID_LONS))
    per_dec = np.full(len(series), np.nan)
    pval = np.full(len(series), np.nan)
    for i, vals in enumerate(series):
        arr = np.array([np.nan if x is None else x for x in vals], dtype=float)
        ok = ~np.isnan(arr)
        if ok.sum() < 10 or np.nanmax(arr) - np.nanmin(arr) < 1e-9:
            continue
        res = mk.original_test(arr[ok])
        per_dec[i] = float(res.slope) * 10
        pval[i] = float(res.p)
    valid = ~np.isnan(per_dec)
    sig = valid & (pval < ALPHA)
    sign = np.where(~valid, 0, np.where(per_dec > 0, 1, np.where(per_dec < 0, -1, 0)))
    finite = np.abs(per_dec[valid])
    vmax = float(np.nanpercentile(finite, 95)) if finite.size else 1.0
    return {"per_decade": per_dec.reshape(shape), "p": pval.reshape(shape), "significant": sig.reshape(shape),
            "sign": sign.reshape(shape), "valid": valid.reshape(shape), "vmax": vmax if vmax > 0 else 1.0,
            "years": [years[0], years[-1]], "source": source, "counts": {
                "valid": int(valid.sum()), "up": int((sign > 0).sum()), "down": int((sign < 0).sum()),
                "up_sig": int((sig & (sign > 0)).sum()), "down_sig": int((sig & (sign < 0)).sum())}}


def trend_map(key: str = "T2M", end_year: int | None = None) -> dict | None:
    """15° ızgarada (11 × 24, GRID_LATS × GRID_LONS) on yıllık değişim ve anlamlılık.

    Dönüş: {"key", "name", "name_en", "unit", "lats", "lons", "per_decade" (np 11×24, NaN = veri yok), "p",
            "significant" (bool), "sign" (+1/−1/0), "valid", "vmax" (simetrik renk ölçeği, |değer|ların %95'i),
            "years", "source", "counts": {valid, up, down, up_sig, down_sig}, "sentence_tr", "sentence_en"}
    `end_year` şimdilik yok sayılır (anlık görüntü sabit dönem); dönem "years" alanında. Veri yoksa None.
    Yıllık ortalamalar üzerinde Mann-Kendall (mevsim etkisi yıllık ortalamayla zaten giderilir).
    """
    v = VARIABLES.get(key)
    if v is None:
        return None
    try:
        m = _trend_map(key)
    except Exception:
        return None
    if m is None:
        return None
    c = m["counts"]
    up_word = {"T2M": ("ısınıyor", "warming"), "TS": ("ısınıyor", "warming")}.get(key, ("artıyor", "increasing"))
    dn_word = {"T2M": ("soğuyor", "cooling"), "TS": ("soğuyor", "cooling")}.get(key, ("azalıyor", "decreasing"))
    y0, y1 = m["years"]
    s_tr = (f"{v[5]} ({y0}–{y1}) · {c['valid']} nokta: {up_word[0]} {c['up']} (anlamlı {c['up_sig']}), "
            f"{dn_word[0]} {c['down']} (anlamlı {c['down_sig']}). Aynı değişken bölgeye göre zıt yönde "
            "değişebiliyor.")
    s_en = (f"{v[6]} ({y0}–{y1}): {c['up']} of {c['valid']} points are {up_word[1]} ({c['up_sig']} significant), "
            f"{c['down']} are {dn_word[1]} ({c['down_sig']} significant). The same variable can change in opposite "
            "directions in different regions.")
    unit = v[2]
    return {"key": key, "name": v[5], "name_en": v[6], "unit": unit, "lats": list(GRID_LATS), "lons": list(GRID_LONS),
            **m, "sentence_tr": s_tr, "sentence_en": s_en}
