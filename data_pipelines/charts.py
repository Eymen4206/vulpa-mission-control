# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Sağ paneldeki değerlere tıklanınca açılan grafik penceresi için çizime hazır veri (Frontend Plotly ile çizer).

`metric_chart(region, metric)` her metrik için aynı şemayı döndürür; renk ve düzen Frontend'e aittir.
Değerler sağ paneldekilerle aynı hesaptan gelir (series.analyze, power._fetch_power). İstisna fırlatmaz.
"""

from __future__ import annotations

import math

import numpy as np
import pymannkendall as mk
import streamlit as st

from .config import ALPHA, END, PERIOD, PROJECTION_MONTHS, START, WEATHER_TTL
from .regions import REGIONS
from .series import analyze, build_series

METRICS = ("tau", "p", "slope", "power_t", "global")
METRIC_ALIASES = {"z": "p", "p_value": "p", "kendall": "tau", "direction": "slope", "decade": "slope",
                  "projection": "slope", "sen": "slope", "temperature_trend": "power_t"}
MONTHS_TR = ("Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")
MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def metric_chart(region: str | None, metric: str, y0: int | None = None, y1: int | None = None) -> dict | None:
    """Tek bir değerin grafiği.

    metric: "tau" (Kendall τ), "p" (p-değeri / z), "slope" (Sen eğilimi, on yıllık değişim, yön, projeksiyon),
            "power_t" (NASA POWER uzun vadeli sıcaklık eğilimi; y0–y1 sağ paneldeki pencere).
    Dönüş:
      {"metric", "kind": "bar"|"density"|"line",
       "title_tr", "title_en", "x_label_tr", "x_label_en", "y_label_tr", "y_label_en",
       "traces": [{"name_tr", "name_en", "x": [...], "y": [...], "style": "bar"|"line"|"dash"|"marker"|"area"}],
       "marks": [{"axis": "x"|"y", "value": float, "label_tr", "label_en"}],   # dikey/yatay referans çizgileri
       "value": float (paneldeki değer), "unit": str,
       "explain_tr", "explain_en" (pencerede gösterilecek 1–2 cümle)}
    Bilinmeyen bölge/metrik ya da hata: None.
    """
    metric = METRIC_ALIASES.get(metric, metric)
    if metric == "global":            # bölgeden bağımsız: küresel yıllık sapma (ÖNERİ #8)
        from .globalstats import global_annual_anomaly
        return global_annual_anomaly()
    if region not in REGIONS or metric not in METRICS:
        return None
    try:
        if metric == "power_t":
            return _power_chart(region, y0, y1)
        return _series_chart(region, metric)
    except Exception:
        return None


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _series_chart(region: str, metric: str) -> dict:
    spec = REGIONS[region]
    values = build_series(region)[spec.variable].to_numpy(dtype=float)
    r = analyze(region)
    unit = spec.unit
    base = {"metric": metric, "unit": unit}

    if metric == "tau":
        taus, ps = [], []
        for m in range(PERIOD):
            res = mk.original_test(values[m::PERIOD])
            taus.append(round(float(res.Tau), 3))
            ps.append(float(res.p))
        sig_tr = [f"p={p:.3f}" for p in ps]
        return {**base, "kind": "bar", "value": round(r["Tau"], 3),
                "title_tr": "Kendall τ · takvim ayına göre", "title_en": "Kendall τ · by calendar month",
                "x_label_tr": "Ay", "x_label_en": "Month", "y_label_tr": "Kendall τ", "y_label_en": "Kendall τ",
                "traces": [{"name_tr": "Aylık τ", "name_en": "Monthly τ", "x": list(MONTHS_TR), "x_en": list(MONTHS_EN),
                            "y": taus, "hover": sig_tr, "style": "bar"}],
                "marks": [{"axis": "y", "value": round(r["Tau"], 3), "label_tr": f"Mevsimsel τ = {r['Tau']:+.3f}",
                           "label_en": f"Seasonal τ = {r['Tau']:+.3f}"},
                          {"axis": "y", "value": 0.0, "label_tr": "Eğilim yok", "label_en": "No trend"}],
                "explain_tr": ("Her çubuk, o takvim ayının yıllar boyunca ne kadar tutarlı arttığını (+) ya da azaldığını "
                               "(−) gösterir. Mevsimsel Mann-Kendall testi bu 12 ayı birleştirir; −1 ile +1 arasındadır."),
                "explain_en": ("Each bar shows how consistently that calendar month rose (+) or fell (−) over the years. "
                               "The seasonal Mann-Kendall test combines these 12 months; it ranges from −1 to +1.")}

    if metric == "p":
        z = float(r["z"])
        lim = max(4.0, abs(z) + 1.0)
        xs = np.linspace(-lim, lim, 241)
        pdf = np.exp(-xs ** 2 / 2) / math.sqrt(2 * math.pi)
        crit = 1.959964
        tail = np.where(np.abs(xs) >= abs(z), pdf, 0.0)
        tiny = float(r["p"]) < 1e-3   # alan gözle görülmeyecek kadar küçük: açıklamada belirtilir
        return {**base, "kind": "density", "value": float(r["p"]), "unit": "",
                "title_tr": "p-değeri · test istatistiği z", "title_en": "p-value · test statistic z",
                "x_label_tr": "z", "x_label_en": "z", "y_label_tr": "Olasılık yoğunluğu", "y_label_en": "Probability density",
                "traces": [{"name_tr": "Eğilim yoksa beklenen dağılım", "name_en": "Expected if no trend",
                            "x": xs.round(3).tolist(), "y": pdf.round(5).tolist(), "style": "line"},
                           {"name_tr": f"p = {r['p']:.4f} (iki taraflı alan)", "name_en": f"p = {r['p']:.4f} (two-sided area)",
                            "x": xs.round(3).tolist(), "y": [float(f"{v:.4g}") for v in tail], "style": "area"}],
                "marks": [{"axis": "x", "value": round(z, 3), "label_tr": f"z = {z:+.2f}", "label_en": f"z = {z:+.2f}"},
                          {"axis": "x", "value": crit, "label_tr": f"α = {ALPHA} sınırı", "label_en": f"α = {ALPHA} limit"},
                          {"axis": "x", "value": -crit, "label_tr": "", "label_en": ""}],
                "explain_tr": ("Gri eğri, gerçekte hiçbir eğilim olmasaydı z'nin dağılımıdır. Gölgeli alan p-değeridir: "
                               f"bu kadar güçlü bir eğilimin rastlantıyla çıkma olasılığı. ±1,96 dışı (p < {ALPHA}) anlamlıdır."
                               + (f" Burada z = {z:+.2f}: alan gözle görülmeyecek kadar küçük, yani eğilimin "
                                  "rastlantı olması çok düşük olasılık." if tiny else "")),
                "explain_en": ("The curve is the distribution of z if there were no trend at all. The shaded area is the "
                               "p-value: the chance of a trend this strong arising by chance. Beyond ±1.96 "
                               f"(p < {ALPHA}) is significant."
                               + (f" Here z = {z:+.2f}: the area is too small to see, i.e. the trend is very unlikely "
                                  "to be chance." if tiny else ""))}

    # slope: yıllık ortalamalar + Sen doğrusu + 2034 projeksiyonu
    n = len(values)
    y_start = int(START[:4])
    years_n = n // PERIOD
    annual = values[:years_n * PERIOD].reshape(years_n, PERIOD).mean(axis=1)
    yrs = list(range(y_start, y_start + years_n))
    t_mid = np.arange(years_n) * PERIOD + (PERIOD - 1) / 2
    sen = r["intercept"] + r["slope"] * t_mid
    t_proj = np.array([n - 1, n - 1 + PROJECTION_MONTHS], dtype=float)
    proj = r["intercept"] + r["slope"] * t_proj
    end_year = int(END[:4])
    proj_x = [end_year + 0.9, end_year + 0.9 + PROJECTION_MONTHS / 12]
    dec = r["slope_year"] * 10
    # %95 güven aralığı (Gilbert 1987, Sen eğimi): yıllık ortalamalar üzerinden ikili eğimlerin sıralı değerleri
    slopes = np.sort([(annual[j] - annual[i]) / (j - i) for i in range(years_n) for j in range(i + 1, years_n)])
    var_s = years_n * (years_n - 1) * (2 * years_n + 5) / 18
    c = 1.96 * math.sqrt(var_s)
    m1 = int(max(0, math.floor((len(slopes) - c) / 2)))
    m2 = int(min(len(slopes) - 1, math.ceil((len(slopes) + c) / 2)))
    ci_low, ci_high = float(slopes[m1]), float(slopes[m2])
    xm, ym = float(np.median(np.arange(years_n))), float(np.median(annual))
    band_low = [round(ym + ci_low * (i - xm), 4) for i in range(years_n)]
    band_high = [round(ym + ci_high * (i - xm), 4) for i in range(years_n)]
    return {**base, "kind": "line", "value": float(r["slope_year"]),
            "ci_low": ci_low, "ci_high": ci_high, "ci_level": 0.95,
            "band": {"style": "band", "x": yrs, "y_low": band_low, "y_high": band_high,
                     "name_tr": "%95 güven aralığı", "name_en": "95% confidence interval"},
            "title_tr": f"Sen eğilimi · {spec.variable}", "title_en": f"Sen slope · {spec.en[0] or region}",
            "x_label_tr": "Yıl", "x_label_en": "Year", "y_label_tr": unit, "y_label_en": unit,
            "traces": [{"name_tr": "Yıllık ortalama", "name_en": "Annual mean", "x": yrs, "y": annual.round(4).tolist(),
                        "style": "marker"},
                       {"name_tr": "Sen doğrusu", "name_en": "Sen line", "x": yrs, "y": sen.round(4).tolist(),
                        "style": "line"},
                       {"name_tr": "Doğrusal uzatım (öngörü değil)", "name_en": "Linear extension (not a forecast)",
                        "x": [round(v, 2) for v in proj_x], "y": proj.round(4).tolist(), "style": "dash"}],
            "marks": [],
            "explain_tr": (f"Sen eğilimi {r['slope_year']:+.4g} {unit}/yıl (on yılda {dec:+.3g} {unit}). Noktalar yıllık "
                           "ortalamalar, çizgi aykırı değerlere dayanıklı Sen doğrusudur; kesikli kısım 2034'e doğrusal "
                           "uzatımdır, bir öngörü değildir. Gölgeli alan yıllık eğimin %95 güven aralığıdır: "
                           f"{ci_low * 10:+.3g} ile {ci_high * 10:+.3g}".replace(".", ",") + f" {unit}/10 yıl (Gilbert, yıllık ortalamalar)."),
            "explain_en": (f"Sen slope {r['slope_year']:+.4g} {unit}/yr ({dec:+.3g} {unit} per decade). Dots are annual "
                           "means; the line is the outlier-resistant Sen line; the dashed part is a linear extension to "
                           "2034, not a forecast. The shaded area is the 95% confidence interval of the annual slope: "
                           f"{ci_low * 10:+.3g} to {ci_high * 10:+.3g} {unit}/decade (Gilbert, annual means).")}


def _power_chart(region: str, y0: int | None, y1: int | None) -> dict | None:
    from .config import LAST_FULL_YEAR, POWER_SPAN
    from .power import _fetch_power, power_years

    if y1 is None:
        y1 = LAST_FULL_YEAR
    if y0 is None:
        y0 = int(y1) - POWER_SPAN + 1
    y0, y1 = power_years(y0, y1)
    pw = _fetch_power(region, y0, y1)
    years, temps = pw.get("years") or [], pw.get("annual_t") or []
    if len(years) < 3:
        return None
    res = mk.original_test(np.asarray(temps, dtype=float))
    line = [round(float(res.intercept) + float(res.slope) * i, 3) for i in range(len(years))]
    return {"metric": "power_t", "kind": "line", "value": round(pw["t_dec"], 3), "unit": "°C/10 yıl",
            "title_tr": f"NASA POWER · yıllık ortalama sıcaklık ({years[0]}–{years[-1]})",
            "title_en": f"NASA POWER · annual mean temperature ({years[0]}–{years[-1]})",
            "x_label_tr": "Yıl", "x_label_en": "Year", "y_label_tr": "°C", "y_label_en": "°C",
            "traces": [{"name_tr": "Yıllık ortalama", "name_en": "Annual mean", "x": years, "y": temps, "style": "marker"},
                       {"name_tr": "Sen doğrusu", "name_en": "Sen line", "x": years, "y": line, "style": "line"}],
            "marks": [{"axis": "y", "value": round(pw["t_mean"], 2), "label_tr": f"Dönem ort. {pw['t_mean']:.1f} °C",
                       "label_en": f"Period mean {pw['t_mean']:.1f} °C"}],
            "live": bool(pw.get("live")), "source": pw.get("source", ""),
            "explain_tr": (f"Eğilim {pw['t_dec']:+.2f} °C/10 yıl (p={pw['t_p']:.3f}). En sıcak yıl {pw['warmest']}."
                           + ("" if pw.get("live") else " Kaynağa ulaşılamadı; simülasyon.")),
            "explain_en": (f"Trend {pw['t_dec']:+.2f} °C/decade (p={pw['t_p']:.3f}). Warmest year {pw['warmest']}."
                           + ("" if pw.get("live") else " Source unavailable; simulated."))}
