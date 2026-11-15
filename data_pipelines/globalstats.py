"""Küresel ve bölgeler arası özetler (ÖNERİ #8–#10). Hepsi depodaki anlık görüntülerden; ağ isteği yok
(compare_regions yalnızca NASA POWER önbelleğini kullanır, bkz. not).
"""

from __future__ import annotations

import numpy as np
import pymannkendall as mk
import streamlit as st

from .annual import BASELINE, load_annual
from .config import ALPHA, GRID_LATS, GRID_LONS, WEATHER_TTL
from .quality import data_quality
from .regions import REGION_LIST, REGIONS
from .series import analyze

# Copernicus C3S (ERA5) 1991–2020 normaline göre küresel yıllık sapmalar — yalnızca doğrulama cümlesi için
COPERNICUS = {2023: 0.60, 2024: 0.72}


def _num_tr(v: float, d: int = 2, signed: bool = True) -> str:
    return (f"{v:+.{d}f}" if signed else f"{v:.{d}f}").replace(".", ",")


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _global_series() -> dict | None:
    pts = load_annual().get("grid", [])
    la, _ = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    if len(pts) != la.size or not all(pts):
        return None
    years = sorted(set.intersection(*(set(p["years"]) for p in pts)))
    w = np.cos(np.radians(la.ravel()))
    anoms = []
    for p in pts:
        t = dict(zip(p["years"], p["T2M"]))
        base = np.mean([t[y] for y in years if BASELINE[0] <= y <= BASELINE[1]])
        anoms.append([t[y] - base for y in years])
    a = np.asarray(anoms)                       # (264, n_years)
    glob = (a * w[:, None]).sum(axis=0) / w.sum()
    return {"years": years, "anomaly": [round(float(v), 3) for v in glob]}


def global_annual_anomaly() -> dict | None:
    """1991–son yıl küresel yıllık sıcaklık sapması; `metric_chart` şemasıyla (metric "global").

    Yöntem: annual.json'daki 264 noktalı 15° ızgara (NASA POWER / MERRA-2, ±75° enlem), her noktada 1991–2020 ortalamasına
    göre sapma, cos(enlem) alan ağırlıklı ortalama. Ek alanlar: "years", "anomaly", "per_decade", "p".
    Anlık görüntü yoksa None. İstisna fırlatmaz.
    """
    try:
        s = _global_series()
    except Exception:
        return None
    if not s:
        return None
    years, an = s["years"], s["anomaly"]
    res = mk.original_test(np.asarray(an))
    line = [round(float(res.intercept) + float(res.slope) * i, 3) for i in range(len(years))]
    dec = float(res.slope) * 10
    last = years[-1]
    cmp_tr = " ".join(f"{y}: {_num_tr(dict(zip(years, an))[y])} °C (Copernicus ERA5 {_num_tr(c)} °C)."
                      for y, c in COPERNICUS.items() if y in years)
    cmp_en = " ".join(f"{y}: {dict(zip(years, an))[y]:+.2f} °C (Copernicus ERA5 {c:+.2f} °C)."
                      for y, c in COPERNICUS.items() if y in years)
    return {
        "metric": "global", "kind": "line", "value": round(dec, 3), "unit": "°C/10 yıl",
        "years": years, "anomaly": an, "per_decade": round(dec, 3), "p": float(res.p),
        "title_tr": f"Küresel yıllık sıcaklık sapması ({years[0]}–{last})",
        "title_en": f"Global annual temperature anomaly ({years[0]}–{last})",
        "x_label_tr": "Yıl", "x_label_en": "Year", "y_label_tr": "°C (1991–2020'ye göre)",
        "y_label_en": "°C (vs 1991–2020)",
        "traces": [{"name_tr": "Yıllık küresel sapma", "name_en": "Annual global anomaly", "x": years, "y": an,
                    "style": "bar"},
                   {"name_tr": "Sen doğrusu", "name_en": "Sen line", "x": years, "y": line, "style": "line"}],
        "marks": [{"axis": "y", "value": 0.0, "label_tr": "1991–2020 ortalaması", "label_en": "1991–2020 mean"}],
        "explain_tr": (f"Dünya on yılda {_num_tr(dec)} °C ısınıyor (Mann-Kendall p = {res.p:.1g}). Yöntem: NASA POWER "
                       "(MERRA-2) yıllık ortalamaları, 264 noktalı 15° ızgara (±75° enlem), her noktada 1991–2020 "
                       f"normaline göre sapma, cos(enlem) ile alan ağırlıklı ortalama. Doğrulama — {cmp_tr} Kutuplar "
                       "(75°'nin ötesi) dahil olmadığı için değerler biraz düşük kalabilir."),
        "explain_en": (f"The planet is warming by {dec:+.2f} °C per decade (Mann-Kendall p = {res.p:.1g}). Method: NASA "
                       "POWER (MERRA-2) annual means on a 264-point 15° grid (±75° latitude), anomaly vs each point's "
                       f"1991–2020 normal, area-weighted by cos(latitude). Validation — {cmp_en} The poles (beyond 75°) "
                       "are excluded, so values may be slightly low."),
    }


def year_extremes(year: int, k: int = 3) -> dict | None:
    """Seçili yılın sene ortalamasında 1991–2020 normaline göre en sıcak ve en soğuk sapmalı k bölge.

    Dönüş: {"year", "hottest": [{"region", "anomaly"}], "coldest": [...], "sentence_tr", "sentence_en"}
    Yıl annual.json'da yoksa (ör. içinde bulunulan yıl) None. İstisna fırlatmaz.
    """
    try:
        year = int(year)
        regions = load_annual().get("regions", {})
        vals = []
        for r in REGION_LIST:
            rec = regions.get(r.name)
            if not rec or year not in rec["years"]:
                continue
            base = [t for y, t in zip(rec["years"], rec["T2M"]) if BASELINE[0] <= y <= BASELINE[1]]
            if len(base) < 20:
                continue
            vals.append((r.name, round(rec["T2M"][rec["years"].index(year)] - float(np.mean(base)), 2)))
        if len(vals) < 2 * k:
            return None
    except Exception:
        return None
    vals.sort(key=lambda v: v[1], reverse=True)
    hot = [{"region": n, "anomaly": a} for n, a in vals[:k]]
    cold = [{"region": n, "anomaly": a} for n, a in sorted(vals[-k:], key=lambda v: v[1])]
    en = {r.name: (r.en[0] or r.name) for r in REGION_LIST}
    hs_tr = ", ".join(f"{h['region']} ({_num_tr(h['anomaly'], 1)} °C)" for h in hot)
    cs_tr = ", ".join(f"{c['region']} ({_num_tr(c['anomaly'], 1)} °C)" for c in cold)
    hs_en = ", ".join(f"{en[h['region']]} ({h['anomaly']:+.1f} °C)" for h in hot)
    cs_en = ", ".join(f"{en[c['region']]} ({c['anomaly']:+.1f} °C)" for c in cold)
    warm_share = sum(1 for _, a in vals if a > 0)
    return {
        "year": year, "hottest": hot, "coldest": cold, "warmer_regions": warm_share, "regions": len(vals),
        "sentence_tr": (f"{year} sene ortalamasında 1991–2020 normaline göre en sıcak bölgeler: {hs_tr}; en soğuk: {cs_tr}. "
                        f"{len(vals)} bölgenin {warm_share}'i normalden sıcaktı (NASA POWER)."),
        "sentence_en": (f"In the {year} annual mean, relative to 1991–2020, the warmest regions were {hs_en}; the coolest "
                        f"{cs_en}. {warm_share} of {len(vals)} regions were warmer than normal (NASA POWER)."),
    }


def compare_regions(a: str, b: str, y0: int | None = None, y1: int | None = None) -> dict | None:
    """İki bölgeyi yan yana karşılaştırır (tema eğilimi, NASA POWER sıcaklık eğilimi, veri güveni).

    Dönüş: {"a", "b", "rows": [{"key", "label_tr", "label_en", "a": str, "b": str}], "sentence_tr", "sentence_en"}
    Tema serileri farklı değişkenler olabildiği için yalnızca sıcaklık eğilimi (NASA POWER, aynı birim) sayısal olarak
    kıyaslanır. POWER, uygulamanın 30 dk önbelleğinden gelir; önbellekte yoksa tek bir istek atılır (anahtar yok).
    Bilinmeyen bölge ya da hata: None. İstisna fırlatmaz.
    """
    if a not in REGIONS or b not in REGIONS or a == b:
        return None
    try:
        from .config import LAST_FULL_YEAR, POWER_SPAN
        from .power import _fetch_power, power_years

        y1 = LAST_FULL_YEAR if y1 is None else int(y1)
        y0 = y1 - POWER_SPAN + 1 if y0 is None else int(y0)
        y0, y1 = power_years(y0, y1)
        info = {}
        for name in (a, b):
            spec, r = REGIONS[name], analyze(name)
            pw = _fetch_power(name, y0, y1)
            q = data_quality(name, None, pw.get("live"), pw.get("short_window"))
            info[name] = {"spec": spec, "r": r, "pw": pw, "q": q}
    except Exception:
        return None
    lv = {"high": ("yüksek", "high"), "medium": ("orta", "medium"), "low": ("düşük", "low")}

    def theme(n, lang):
        s, r = info[n]["spec"], info[n]["r"]
        sig = r["p"] < ALPHA
        var = s.variable if lang == "tr" else (s.en[2] or s.variable)
        dec = r["slope_year"] * 10
        val = _num_tr(dec, 3 if abs(dec) < 0.1 else 2) if lang == "tr" else (f"{dec:+.3f}" if abs(dec) < 0.1 else f"{dec:+.2f}")
        tag = ("anlamlı" if sig else "anlamsız") if lang == "tr" else ("significant" if sig else "not significant")
        per = "/10 yıl" if lang == "tr" else "/decade"
        return f"{var}: {val} {s.unit}{per} ({tag})"

    def power(n, lang):
        pw = info[n]["pw"]
        sim = "" if pw.get("live") else (" · simülasyon" if lang == "tr" else " · simulated")
        return (f"{_num_tr(pw['t_dec'])} °C/10 yıl{sim}" if lang == "tr" else f"{pw['t_dec']:+.2f} °C/decade{sim}")

    rows = [
        {"key": "theme", "label_tr": "Tema eğilimi", "label_en": "Theme trend",
         "a": theme(a, "tr"), "b": theme(b, "tr"), "a_en": theme(a, "en"), "b_en": theme(b, "en")},
        {"key": "power", "label_tr": f"Sıcaklık eğilimi ({y0}–{y1})", "label_en": f"Temperature trend ({y0}–{y1})",
         "a": power(a, "tr"), "b": power(b, "tr"), "a_en": power(a, "en"), "b_en": power(b, "en")},
        {"key": "quality", "label_tr": "Veri güveni", "label_en": "Data confidence",
         "a": lv[info[a]["q"]["level"]][0], "b": lv[info[b]["q"]["level"]][0],
         "a_en": lv[info[a]["q"]["level"]][1], "b_en": lv[info[b]["q"]["level"]][1]},
    ]
    ta, tb = info[a]["pw"]["t_dec"], info[b]["pw"]["t_dec"]
    fast, slow = (a, b) if ta >= tb else (b, a)
    tf, ts = max(ta, tb), min(ta, tb)
    en_name = {n: (REGIONS[n].en[0] or n) for n in (a, b)}
    if abs(ta - tb) < 0.05:
        s_tr = (f"{a} ve {b} benzer hızda ısınıyor ({_num_tr(ta)} ve {_num_tr(tb)} °C/10 yıl, NASA POWER {y0}–{y1}).")
        s_en = (f"{en_name[a]} and {en_name[b]} are warming at a similar rate ({ta:+.2f} and {tb:+.2f} °C/decade, "
                f"NASA POWER {y0}–{y1}).")
    else:
        s_tr = (f"{fast}, {slow} bölgesinden daha hızlı ısınıyor: {_num_tr(tf)} ve {_num_tr(ts)} °C/10 yıl "
                f"(NASA POWER {y0}–{y1}).")
        s_en = (f"{en_name[fast]} is warming faster than {en_name[slow]}: {tf:+.2f} vs {ts:+.2f} °C/decade "
                f"(NASA POWER {y0}–{y1}).")
    return {"a": a, "b": b, "rows": rows, "sentence_tr": s_tr, "sentence_en": s_en, "window": [y0, y1]}


# ── Seiron bağlamı: tüm bölgelerin kısa özeti (15.11.2026) ───────────────────────────────────────────────────────
_ARROW = {"increasing": "↑", "decreasing": "↓", "no trend": "→"}


def regions_brief(focus: tuple[str, ...] | list[str] = (), lang: str = "tr") -> str:
    """Seiron sistem istemi için TÜM bölgelerin tema eğilimini kısa biçimde verir (dil modeli istek boyutunu korur).

    104 bölgede eski satır başı biçimin (~3,1 bin token) üçte biri kadar: bölgeler değişkene göre gruplanır, her bölge
    yalnızca "Ad ↑*" olarak yazılır (* = Mann-Kendall p < 0,05). `focus` içindeki bölgeler (seçili + anılan) ayrıca
    eğim değeriyle tam satır alır. Analizler `analyze` önbelleğinden gelir; ağ isteği yok, istisna fırlatmaz.
    Dönüş: düz metin ("" hata durumunda).
    """
    en = lang == "en"
    try:
        groups: dict[tuple[str, str], list[str]] = {}
        full = []
        for r in REGION_LIST:
            a = analyze(r.name)
            sig = a["p"] < ALPHA
            name = (r.en[0] or r.name) if en else r.name
            groups.setdefault((r.variable, r.unit), []).append(f"{name} {_ARROW.get(a['trend'], '→')}{'*' if sig else ''}")
            if r.name in focus:
                dec = a["slope_year"] * 10
                full.append(f"{name}: {r.variable} ({r.unit}) {_ARROW.get(a['trend'], '→')} "
                            + (f"{dec:+.3g} {r.unit}/decade, p = {a['p']:.3f}" if en else
                               f"{_num_tr(dec, 3)} {r.unit}/10 yıl, p = {_num_tr(a['p'], 3, False)}"))
        head = (f"{len(REGION_LIST)} regions, theme-series trend 2000–2024 (↑ increasing, ↓ decreasing, → none; "
                "* significant, p < 0.05):" if en else
                f"{len(REGION_LIST)} bölge, tema serisi eğilimi 2000–2024 (↑ artış, ↓ azalış, → yok; * anlamlı, p < 0,05):")
        body = "\n".join(f"- {var} ({unit}): " + ", ".join(items) for (var, unit), items in groups.items())
        tail = ("\nFocus regions: " if en else "\nOdaktaki bölgeler: ") + "; ".join(full) if full else ""
        return head + "\n" + body + tail
    except Exception:
        return ""
