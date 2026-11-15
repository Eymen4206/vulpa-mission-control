# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Jüri turu vitrin bölgeleri (ÖNERİ #7): en güvenilir ve en açıklayıcı gerçek veri bölgeleri + tek cümlelik özet.

Seçim yalnızca gerçek seriye ve istatistiğe dayanır (Groq ve ağ isteği yok):
  1) Gerçek seri, veri güveni "high" (seri ölçütleri), anlamlı eğilim (p < 0,05).
  2) Güçlü eğilimden zayıfa (|z|) sıralanır; her adımda daha önce seçilmemiş veri ailesi ve kıta tercih edilir.
  3) Yeterli aday yoksa ölçütler sırayla gevşetilir (önce aile/kıta çeşitliliği, sonra "medium" güven).
"""

from __future__ import annotations

import streamlit as st

from .config import ALPHA, END, START, WEATHER_TTL
from .quality import data_quality
from .real_series import REAL_SOURCES
from .regions import REGIONS
from .series import analyze

# Seri türü → aile (çeşitlilik için) ve tur katmanı önerisi
FAMILY = {"t2m": "temperature", "t2m_anom": "temperature", "ts_anom": "temperature", "t2m_max": "temperature",
          "precip": "water", "spei3": "water", "aod": "air", "sst": "ocean", "co2": "carbon", "seaice_s": "ice"}
KIND_EN = {"t2m": "monthly mean 2 m air temperature", "t2m_anom": "2 m temperature anomaly",
           "ts_anom": "surface (skin) temperature anomaly", "t2m_max": "monthly maximum 2 m temperature",
           "precip": "monthly total precipitation", "spei3": "SPEI-3 drought index",
           "aod": "aerosol optical depth (550 nm)", "sst": "sea surface temperature",
           "co2": "atmospheric CO₂ at Mauna Loa", "seaice_s": "Southern Hemisphere sea-ice extent"}


def _continent(lat: float, lon: float) -> str:
    """Kaba kıta/bölge sınıfı (yalnızca çeşitlilik için)."""
    if lat < -60:
        return "antarctica"
    if lat > 66:
        return "arctic"
    if -170 <= lon < -30:
        return "south_america" if lat < 13 else "north_america"
    if -30 <= lon < 60:
        if lat >= 35:
            return "europe"
        return "africa" if lon < 42 or lat < 12 else "asia"
    if lat < -10 and lon >= 110:
        return "oceania"
    return "asia"


def _fmt(v: float) -> str:
    a = abs(v)
    return f"{v:+.3f}" if a < 0.1 else (f"{v:+.2f}" if a < 10 else f"{v:+.1f}")


def _sentences(region: str, kind: str, r: dict) -> tuple[str, str]:
    spec = REGIONS[region]
    dec = r["slope_year"] * 10
    y0, y1 = START[:4], END[:4]
    p_tr = "p < 0,001" if r["p"] < 0.001 else f"p = {r['p']:.3f}".replace(".", ",")
    p_en = "p < 0.001" if r["p"] < 0.001 else f"p = {r['p']:.3f}"
    up = dec > 0
    var = spec.variable
    if var[:1].isupper() and not var[1:2].isupper():      # cümle içi: yalnızca ilk harf küçülür (Türkçe I/İ)
        var = {"I": "ı", "İ": "i"}.get(var[0], var[0].lower()) + var[1:]
    amount = _fmt(abs(dec)).lstrip("+")
    tau_tr = f"{r['Tau']:+.2f}".replace(".", ",")
    tr = (f"{region}: {var} {y0}–{y1} arasında on yılda {amount.replace('.', ',')} {spec.unit} "
          f"{'arttı' if up else 'azaldı'} (mevsimsel Mann-Kendall, {p_tr}, τ = {tau_tr}).")
    name_en = spec.en[0] or region
    en = (f"{name_en}: {KIND_EN.get(kind, spec.variable)} {'rose' if up else 'fell'} by {amount} {spec.unit} per "
          f"decade over {y0}–{y1} (seasonal Mann-Kendall, {p_en}, τ = {r['Tau']:+.2f}).")
    return tr, en


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def _candidates() -> list[dict]:
    out = []
    for name, kind in REAL_SOURCES.items():
        if name not in REGIONS:
            continue
        try:
            r = analyze(name)
            q = data_quality(name)
        except Exception:
            continue
        if q is None:
            continue
        spec = REGIONS[name]
        out.append({"region": name, "kind": kind, "family": FAMILY.get(kind, kind), "level": q["level"],
                    "p": r["p"], "z": abs(r["z"]), "r": r, "continent": _continent(spec.lat, spec.lon)})
    out.sort(key=lambda c: c["z"], reverse=True)
    return out


def showcase_regions(n: int = 5) -> list[dict]:
    """Jüri turu için n vitrin bölgesi (güçlü ve güvenilir eğilim, farklı veri aileleri ve kıtalar).

    Dönüş: [{"region", "kind", "family", "continent", "level", "layer": "thermal"|"classic",
             "chart": "slope"|"tau", "sentence_tr", "sentence_en", "p", "tau", "per_decade", "unit"}]
    `chart`: eğilim tek yönlü ve güçlüyse "slope" (Sen doğrusu en anlaşılır grafik), aksi hâlde "tau".
    `layer`: sıcaklık ve okyanus aileleri için "thermal", diğerleri "classic". İstisna fırlatmaz.
    """
    try:
        cands = [c for c in _candidates() if c["p"] < ALPHA]
    except Exception:
        return []
    picked: list[dict] = []
    # (izin verilen güven seviyeleri, aile tekrarına izin, kıta tekrarına izin) — sırayla gevşer.
    # Yeni bir veri ailesi (okyanus, CO₂, buz) "medium" güvende bile aynı ailenin 3. bölgesinden daha öğreticidir.
    rules = ((("high",), False, False), (("high",), False, True), (("high", "medium"), False, True),
             (("high",), True, True), (("high", "medium"), True, True))
    for levels, fam_ok, cont_ok in rules:
        for c in cands:
            if len(picked) >= n:
                break
            if c in picked or c["level"] not in levels:
                continue
            if not fam_ok and c["family"] in {p["family"] for p in picked}:
                continue
            if not cont_ok and c["continent"] in {p["continent"] for p in picked}:
                continue
            picked.append(c)
    result = []
    for c in picked[:n]:
        r = c["r"]
        tr, en = _sentences(c["region"], c["kind"], r)
        result.append({"region": c["region"], "kind": c["kind"], "family": c["family"], "continent": c["continent"],
                       "level": c["level"], "layer": "thermal" if c["family"] in ("temperature", "ocean") else "classic",
                       "chart": "slope" if abs(r["Tau"]) >= 0.2 else "tau",
                       "sentence_tr": tr, "sentence_en": en, "p": r["p"], "tau": round(r["Tau"], 3),
                       "per_decade": r["slope_year"] * 10, "unit": REGIONS[c["region"]].unit})
    return result
