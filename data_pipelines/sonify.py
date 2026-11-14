"""Trendi dinle (veri sonifikasyonu): bölgenin tema serisi kısa bir ezgiye dönüşür.

- Her yıl bir nota: yıllık ortalama değer → perde (logaritmik ölçek, 220–880 Hz, iki oktav). Yükselen seri tizleşir.
  Ölçek serinin kendi min–max aralığıdır; bölgeler arası perdeler karşılaştırılamaz.
- Sen eğilim doğrusu alçak, kısık bir "taban" sesi olarak çalar (220→… Hz aynı ölçekle).
- Eğilim anlamlıysa (p < 0,05) her notanın başında hafif bir vuruş (yüksek, çok kısa nota) ritmi belirginleştirir.
Frontend `window.__vpAudio` motoruyla çalar. Ağ isteği yok; istisna fırlatmaz.
"""

from __future__ import annotations

import math

import numpy as np
import streamlit as st

from .config import ALPHA, PERIOD, START, WEATHER_TTL
from .regions import REGIONS
from .series import analyze, build_series

F_LOW, F_HIGH = 220.0, 880.0
STEP = 0.4            # saniye / yıl  (25 yıl ≈ 10 sn)


def _freq(v: float, lo: float, hi: float) -> float:
    x = 0.5 if hi - lo < 1e-12 else (v - lo) / (hi - lo)
    x = min(max(x, 0.0), 1.0)
    return round(F_LOW * (F_HIGH / F_LOW) ** x, 2)


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _sonify(region: str) -> dict:
    spec = REGIONS[region]
    values = build_series(region)[spec.variable].to_numpy(dtype=float)
    r = analyze(region)
    years_n = len(values) // PERIOD
    annual = values[:years_n * PERIOD].reshape(years_n, PERIOD).mean(axis=1)
    t_mid = np.arange(years_n) * PERIOD + (PERIOD - 1) / 2
    sen = r["intercept"] + r["slope"] * t_mid
    lo, hi = float(min(annual.min(), sen.min())), float(max(annual.max(), sen.max()))
    y0 = int(START[:4])
    significant = r["p"] < ALPHA
    notes = []
    for i, (v, s) in enumerate(zip(annual, sen)):
        t = round(i * STEP, 3)
        notes.append({"t": t, "dur": round(STEP * 0.9, 3), "freq": _freq(float(v), lo, hi), "gain": 0.55,
                      "role": "data", "year": y0 + i, "value": round(float(v), 4)})
        notes.append({"t": t, "dur": STEP, "freq": round(_freq(float(s), lo, hi) / 2, 2), "gain": 0.18,
                      "role": "trend", "year": y0 + i})
        if significant:
            notes.append({"t": t, "dur": 0.04, "freq": 1760.0, "gain": 0.12, "role": "pulse", "year": y0 + i})
    direction = {"increasing": ("yükseliyor", "rises"), "decreasing": ("alçalıyor", "falls")}.get(
        r["trend"], ("belirgin bir yön izlemiyor", "follows no clear direction"))
    sig_tr = "Eğilim anlamlı olduğu için her yılda hafif bir vuruş duyulur." if significant else \
        "Eğilim istatistiksel olarak anlamlı değil; vuruş yok."
    sig_en = "Because the trend is significant, a soft tick marks every year." if significant else \
        "The trend is not statistically significant; no tick."
    return {
        "region": region, "notes": notes, "bpm": round(60 / STEP), "duration": round(years_n * STEP, 2),
        "years": [y0, y0 + years_n - 1], "unit": spec.unit, "min": round(lo, 4), "max": round(hi, 4),
        "significant": significant,
        "explain_tr": (f"Her nota bir yılın ortalamasıdır ({y0}–{y0 + years_n - 1}); değer arttıkça ses incelir. "
                       f"Alçak taban sesi Sen eğilim doğrusudur ve {direction[0]}. {sig_tr}"),
        "explain_en": (f"Each note is one year's mean ({y0}–{y0 + years_n - 1}); higher values sound higher. "
                       f"The low drone is the Sen trend line and it {direction[1]}. {sig_en}"),
    }


def sonify(region: str) -> dict | None:
    """Bölgenin tema serisinin ezgisi.

    Dönüş: {"notes": [{"t" sn, "dur" sn, "freq" Hz, "gain" 0–1, "role": "data"|"trend"|"pulse", "year", ["value"]}],
            "bpm", "duration" (sn, ≈10), "years": [ilk, son], "unit", "min", "max", "significant",
            "explain_tr", "explain_en"}
    En fazla 75 nota, ≈10 sn. `role` ile Frontend farklı dalga biçimi seçebilir (data: sinüs/üçgen, trend: alçak sinüs,
    pulse: kısa tık). Bilinmeyen bölge ya da hata: None.
    """
    if region not in REGIONS:
        return None
    try:
        out = _sonify(region)
        return out if all(math.isfinite(n["freq"]) for n in out["notes"]) else None
    except Exception:
        return None
