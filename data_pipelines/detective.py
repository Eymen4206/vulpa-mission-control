"""Dedektif sihirbazı (Büyük Plan, Aşama C · madde 4): "Neyi merak ediyorsun? Nerede? Ne kadar geriye?"

Kural tabanlı ve açıklamalı öneriler: bölge türü (çöl, yağmur ormanı, şehir…) × konu (ısınma, su, hava kirliliği…)
→ değişken. Ön izleme sayıları `snapshots/regionvars.json` dosyasından gelir (tüm bölgeler × 15 değişken, NASA POWER yıllık
değerleri); uygulama ağ isteği yapmaz. Yenilemek için:  .venv\\Scripts\\python -m data_pipelines.refresh_regionvars
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pymannkendall as mk
import streamlit as st

from .config import ALPHA, WEATHER_TTL
from .regions import REGION_LIST, REGIONS
from .variables import VARIABLES

REGIONVARS_PATH = Path(__file__).with_name("snapshots") / "regionvars.json"

# Bölge türleri (bir bölge birden fazla türde olabilir)
REGION_TYPES: dict[str, tuple[str, ...]] = {
    "Marmara Havzası": ("city", "coast"), "Batı Avrupa Ovası": ("agriculture",), "Britanya Adaları": ("coast",),
    "Sibirya Taygası": ("taiga",), "Akdeniz Maki Kuşağı": ("coast", "agriculture"), "İber Platosu": ("agriculture",),
    "Apenin Yarımadası": ("agriculture", "coast"), "Alp Kuşağı": ("mountain",),
    "Antarktika Yarımadası": ("polar", "ocean"), "Grönland Buz Tabakası": ("polar",),
    "Nil Deltası ve Vadisi": ("desert", "agriculture", "coast"), "Arap Körfezi Kıyı Çölü": ("desert", "coast", "city"),
    "Necd Platosu": ("desert",), "İran Platosu": ("desert", "mountain"), "Sahra Çölü": ("desert",),
    "Doğu Afrika Savanları": ("savanna",), "Cape Floristik Bölgesi": ("coast", "agriculture"),
    "Nijer Deltası": ("coast", "rainforest"), "Kongo Havzası": ("rainforest",), "Etiyopya Yaylası": ("mountain", "agriculture"),
    "Kanto Ovası": ("city", "coast"), "Kuzey Çin Ovası": ("city", "agriculture"), "Kore Yarımadası": ("city", "coast"),
    "Yangtze Deltası": ("city", "coast"), "Batı Ghatlar": ("mountain", "rainforest"),
    "Hint-Ganj Ovası": ("agriculture", "city"), "İndus Havzası": ("agriculture", "desert"),
    "Ganj-Brahmaputra Deltası": ("coast", "agriculture"), "Chao Phraya Deltası": ("coast", "city"),
    "Malakka Boğazı": ("ocean", "coast"), "Cava Kuzey Kıyısı": ("coast", "city"), "Filipin Denizi": ("ocean",),
    "Moğol Bozkırı ve Gobi": ("desert", "savanna"), "Büyük Set Resifi": ("ocean",),
    "Mauna Loa (Kuzey Pasifik)": ("ocean", "mountain"), "ABD Doğu Kıyısı": ("coast", "city"),
    "Kanada Kuzey Ormanları": ("taiga",), "Meksika Vadisi": ("city", "mountain"), "Kaliforniya Çaparalı": ("coast",),
    "Büyük Göller Havzası": ("agriculture",), "Florida Everglades": ("coast",), "Pasifik Kıyı Dağları": ("mountain", "coast"),
    "Alaska Permafrost Kuşağı": ("polar", "taiga"), "Amazon Havzası": ("rainforest",), "Atlantik Ormanı": ("rainforest", "coast"),
    "Pampa Ovaları": ("agriculture",), "Humboldt Akıntısı": ("ocean", "coast"), "Orta Şili": ("agriculture", "mountain"),
    "Kuzey And Paramoları": ("mountain",), "Tropikal And Buzulları": ("mountain", "polar"),
    # 15.11.2026: yeni bölgeler
    "İskandinav Dağları": ("mountain", "taiga"),
    "Polonya-Baltık Ovası": ("agriculture",),
    "Pannonya Ovası": ("agriculture",),
    "Karadeniz Bozkırları": ("agriculture", "savanna"),
    "Svalbard ve Barents Denizi": ("polar", "ocean"),
    "Hudson Körfezi": ("polar", "ocean"),
    "Kanada Arktik Takımadaları": ("polar",),
    "Yakutistan Permafrostu": ("taiga", "polar"),
    "Ross Buz Sahanlığı": ("polar",),
    "Bereketli Hilal": ("agriculture", "desert"),
    "Kafkas Dağları": ("mountain", "polar"),
    "Aral Gölü Havzası": ("desert",),
    "Kazak Bozkırı": ("savanna", "agriculture"),
    "Tibet Platosu": ("mountain", "polar"),
    "Taklamakan Çölü": ("desert",),
    "Amur Havzası": ("taiga", "agriculture"),
    "Okhotsk Denizi": ("ocean", "polar"),
    "İnci Nehri Deltası": ("city", "coast"),
    "Mekong Deltası": ("coast", "agriculture"),
    "Borneo Yağmur Ormanları": ("rainforest",),
    "Arap Denizi": ("ocean",),
    "Bengal Körfezi": ("ocean",),
    "Maldivler": ("ocean", "coast"),
    "Yeni Gine Dağları": ("mountain", "rainforest"),
    "Murray-Darling Havzası": ("agriculture",),
    "Orta Avustralya Çölü": ("desert",),
    "Güneybatı Avustralya": ("agriculture", "coast"),
    "Yeni Zelanda Güney Alpleri": ("mountain", "polar"),
    "Tasman Denizi": ("ocean",),
    "Ekvatoral Pasifik (Niño 3.4)": ("ocean",),
    "Kuzeydoğu Pasifik": ("ocean",),
    "Kuzey Atlantik Soğuk Lekesi": ("ocean",),
    "Karayip Denizi": ("ocean", "coast"),
    "Meksika Körfezi": ("ocean", "coast"),
    "Benguela Akıntısı": ("ocean", "coast"),
    "Batı Sahel": ("savanna", "desert"),
    "Gine Körfezi Ormanları": ("rainforest", "agriculture"),
    "Çad Gölü Havzası": ("desert", "savanna"),
    "Afrika Boynuzu": ("desert", "savanna"),
    "Kızıldeniz": ("ocean", "coast"),
    "Atlas Dağları": ("mountain", "agriculture"),
    "Madagaskar Yaylası": ("mountain", "rainforest"),
    "Zambezi Havzası": ("savanna",),
    "Highveld (Johannesburg)": ("city",),
    "Büyük Ovalar": ("agriculture", "savanna"),
    "Sonora Çölü": ("desert", "city"),
    "Colorado Kayalık Dağları": ("mountain",),
    "Orta Amerika Kuru Koridoru": ("agriculture", "mountain"),
    "Patagonya Buz Alanları": ("mountain", "polar"),
    "Atacama Çölü": ("desert", "mountain"),
    "Cerrado Savanları": ("savanna", "agriculture"),
    "Pantanal Sulak Alanı": ("savanna", "coast"),
    "Caatinga": ("desert", "savanna"),
    "Orinoko Llanos Ovası": ("savanna", "agriculture"),
}
TYPE_NAMES = {
    "desert": ("Çöl", "Desert"), "rainforest": ("Yağmur ormanı", "Rainforest"), "city": ("Büyük şehir", "Big city"),
    "coast": ("Kıyı ve haliç", "Coast & estuary"), "polar": ("Kutup ve buzul", "Polar & glacier"),
    "mountain": ("Dağ", "Mountain"), "agriculture": ("Tarım ovası", "Farmland"), "ocean": ("Okyanus", "Ocean"),
    "savanna": ("Savan ve bozkır", "Savanna & steppe"), "taiga": ("Tayga ve kuzey ormanı", "Taiga & boreal forest"),
}
TOPICS = {
    "warming": (("Isınma", "Warming"), ("T2M", "T2M_MAX", "T2M_MIN", "TS")),
    "water": (("Su ve kuraklık", "Water & drought"), ("PRECTOTCORR", "GWETROOT", "EVLAND", "GWETTOP", "RH2M")),
    "air": (("Hava kirliliği ve güneş", "Air pollution & sunlight"), ("AOD_55", "ALLSKY_SFC_SW_DWN", "CLOUD_AMT")),
    "ice": (("Buz ve kar", "Ice & snow"), ("SNODP", "TS", "T2M")),
    "land": (("Bitki ve toprak", "Plants & soil"), ("GWETROOT", "GWETTOP", "EVLAND", "PRECTOTCORR")),
    "unsure": (("Emin değilim — şaşırt beni", "Not sure — surprise me"), tuple(VARIABLES)),
}
PERIODS = {"10": (10, ("Son 10 yıl", "Last 10 years")), "25": (25, ("Son 25 yıl", "Last 25 years"))}

# Bölge türüne göre gerekçe (değişkenin genel gerekçesi her yere uymuyor: tropik denize "buz eriyor" yazılmamalı)
WHY_BY_TYPE: dict[tuple[str, str], tuple[str, str]] = {
    ("TS", "ocean"): ("Deniz yüzeyi ısındıkça mercanlar ve deniz yaşamı strese girer, fırtınalar daha çok enerji alır.",
                      "A warmer sea surface stresses corals and marine life and gives storms more energy."),
    ("TS", "desert"): ("Çıplak çöl yüzeyi gündüz çok hızlı ısınır; yüzey sıcaklığı aşırı sıcakların erken göstergesidir.",
                       "Bare desert ground heats very fast by day; skin temperature is an early sign of extreme heat."),
    ("TS", "city"): ("Asfalt ve beton yüzeyi havadan sıcak tutar; kentsel ısı adasını en iyi yüzey sıcaklığı gösterir.",
                     "Asphalt and concrete keep the surface hotter than the air; skin temperature shows the urban heat "
                     "island best."),
    ("T2M", "ocean"): ("Okyanus üstündeki hava ısındıkça daha çok nem taşır; fırtınaların yakıtı artar.",
                       "Warmer air over the ocean carries more moisture, adding fuel to storms."),
    ("T2M", "city"): ("Kentlerde ısı adası etkisi küresel ısınmaya eklenir; ısınma daha hızlı olabilir.",
                      "In cities the heat-island effect adds to global warming, so warming can be faster."),
}
SNOW_MIN_CM = 1.0   # "Buz ve kar" önerilerinde: yıllık ortalama kar derinliği hiç bunu aşmayan bölge kar bölgesi sayılmaz


def detective_questions(lang: str = "tr") -> list[dict]:
    """Sihirbazın 3 sorusu: [{"id", "question", "options": [{"value", "label"}]}]."""
    i = 1 if lang == "en" else 0
    return [
        {"id": "topic", "question": ("Neyi merak ediyorsun?", "What are you curious about?")[i],
         "options": [{"value": k, "label": v[0][i]} for k, v in TOPICS.items()]},
        {"id": "place", "question": ("Nerede?", "Where?")[i],
         "options": [{"value": k, "label": v[i]} for k, v in TYPE_NAMES.items()]
         + [{"value": "globe", "label": ("Kürede kendim seçeceğim", "I'll pick on the globe")[i]},
            {"value": "any", "label": ("Fark etmez", "Anywhere")[i]}]},
        {"id": "period", "question": ("Ne kadar geriye bakalım?", "How far back?")[i],
         "options": [{"value": k, "label": v[1][i]} for k, v in PERIODS.items()]},
    ]


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def load_regionvars() -> dict:
    try:
        return json.loads(REGIONVARS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _preview(region: str, key: str, n_years: int) -> dict | None:
    snap = load_regionvars()
    rec = (snap.get("regions") or {}).get(region)
    if not rec or key not in rec:
        return None
    y0, y1 = snap["years"]
    vals = rec[key][-n_years:]
    arr = np.array([np.nan if x is None else x for x in vals], dtype=float)
    ok = ~np.isnan(arr)
    if ok.sum() < 8 or np.nanmax(arr) - np.nanmin(arr) < 1e-9:
        return None
    res = mk.original_test(arr[ok])
    return {"per_decade": float(res.slope) * 10, "p": float(res.p), "significant": float(res.p) < ALPHA,
            "tau": float(res.Tau), "years": [y1 - len(vals) + 1, y1]}


def detective_suggest(answers: dict, lang: str = "tr", k: int = 4) -> list[dict]:
    """Yanıtlara göre 3–5 öneri: [{"region", "key", "variable", "unit", "type", "reason", "preview": {per_decade, p,
    significant, tau, years} | None, "sentence"}].

    answers: {"topic": TOPICS anahtarı, "place": TYPE_NAMES anahtarı | "any" | "globe", "period": "10" | "25"}.
    "globe" seçildiyse liste boş döner (kullanıcı kürede nokta seçecek; değişken önerisi için `topic_variables`).
    Sıralama: anlamlı eğilimler önce, sonra |τ| büyükten küçüğe; her bölge en fazla bir kez.
    """
    i = 1 if lang == "en" else 0
    topic = answers.get("topic", "unsure")
    place = answers.get("place", "any")
    n_years = PERIODS.get(str(answers.get("period", "25")), PERIODS["25"])[0]
    if place == "globe":
        return []
    keys = TOPICS.get(topic, TOPICS["unsure"])[1]
    regions = [r.name for r in REGION_LIST if place in ("any", None) or place in REGION_TYPES.get(r.name, ())]
    if topic == "ice":   # kar almayan bölgeler (ör. Madagaskar Yaylası) buz/kar konusunda önerilmez; kutup bölgeleri kalır
        snap = (load_regionvars().get("regions") or {})

        def snowy(reg):
            vals = [x for x in (snap.get(reg) or {}).get("SNODP") or [] if x is not None]
            return (max(vals) if vals else 0.0) >= SNOW_MIN_CM or "polar" in REGION_TYPES.get(reg, ())
        regions = [r for r in regions if snowy(r)]
    cands = []
    for reg in regions:
        types = REGION_TYPES.get(reg, ())
        for key in keys:
            v = VARIABLES[key]
            fit = place in v[11] if place not in ("any", None) else any(t in v[11] for t in types)
            pv = _preview(reg, key, n_years)
            if pv is None:
                continue
            score = (2 if pv["significant"] else 0) + abs(pv["tau"]) + (0.5 if fit else 0)
            if topic == "ice" and key == "SNODP":
                score += 0.7   # buz/kar konusunda kar derinliği (varsa) sıcaklıktan önce gelir
            cands.append((score, reg, key, pv, fit))
    cands.sort(key=lambda c: c[0], reverse=True)
    out, used = [], set()
    for score, reg, key, pv, fit in cands:
        if reg in used:
            continue
        used.add(reg)
        v = VARIABLES[key]
        spec = REGIONS[reg]
        tname = ", ".join(TYPE_NAMES[t][i].lower() for t in REGION_TYPES.get(reg, ()))
        unit = v[2] if i == 0 else v[2].replace("mm/ay", "mm/month").replace("gün", "day")
        if v[2] == "0–1":
            unit = ("birim (0–1 ölçeği)", "units (0–1 scale)")[i]
        dec = pv["per_decade"]
        val = f"{dec:+.3g}"
        sig = (("anlamlı" if pv["significant"] else "henüz anlamlı değil"),
               ("significant" if pv["significant"] else "not yet significant"))[i]
        name = (v[5], v[6])[i]
        rname = spec.name if i == 0 else (spec.en[0] or spec.name)
        rtypes = REGION_TYPES.get(reg, ())
        if place in rtypes:   # kullanıcı yer türü seçtiyse yalnızca o türün gerekçesi (yoksa genel gerekçe)
            ptype = place if (key, place) in WHY_BY_TYPE else None
        else:                 # "fark etmez": bölgenin türlerinden uygun olan
            ptype = next((t for t in rtypes if (key, t) in WHY_BY_TYPE), None)
        why = WHY_BY_TYPE[(key, ptype)][i] if ptype else (v[9], v[10])[i]
        reason = (f"{rname} ({tname}): {why}" if i == 0 else f"{rname} ({tname}): {why}")
        sentence = (f"{rname} · {name}: on yılda {val.replace('.', ',')} {unit} ({pv['years'][0]}–{pv['years'][1]}, {sig})."
                    if i == 0 else
                    f"{rname} · {name}: {val} {unit} per decade ({pv['years'][0]}–{pv['years'][1]}, {sig}).")
        out.append({"region": reg, "key": key, "variable": name, "unit": unit, "type": list(REGION_TYPES.get(reg, ())),
                    "reason": reason, "preview": pv, "sentence": sentence, "fit": fit})
        if len(out) >= k:
            break
    return out


def topic_variables(topic: str, lang: str = "tr") -> list[dict]:
    """Bir konu için önerilen değişkenler (kürede nokta seçen kullanıcı için): [{"key", "name", "why"}]."""
    i = 1 if lang == "en" else 0
    return [{"key": k, "name": VARIABLES[k][5 + i], "why": VARIABLES[k][9 + i]}
            for k in TOPICS.get(topic, TOPICS["unsure"])[1]]


def regionvars_annual(points: dict, y0: int, y1: int) -> None:
    """refresh_regionvars yardımcısı: {bölge: {değişken: [yıllık]}} yazar."""
    from datetime import datetime, timezone
    REGIONVARS_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGIONVARS_PATH.write_text(json.dumps({
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": "NASA POWER monthly (MERRA-2) — yıllık değerler (YYYY13)", "years": [y0, y1], "regions": points},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
