# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Ek ölçüm veri setleri (uydu ve yer ölçümleri) — bölge bazında, anlık görüntüden.

Proje sahibinin isteği: yarışmanın saydığı uydu/ölçüm kaynaklarını eklemek (NSIDC Arktik deniz buzu, GPM IMERG,
PSMSL deniz seviyesi, GRACE, GLDAS, OMI, AIRS, MODIS). Her veri seti `snapshots/extra_series.json` dosyasına bir kez
yazılır (yenileme betikleri: refresh_extra.py); uygulama yalnızca dosyayı okur, token ya da kota kullanmaz.

Dönem: değişken seçiciyle aynı (variables._window: son 25 tam yıl, 2001–2025). Aylık 300 değer; eksik %10'u aşarsa
analiz yapılmaz (available=False). Analiz şeması `variable_analysis` ile birebir aynıdır (build_analysis).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from .config import WEATHER_TTL
from .regions import REGIONS

EXTRA_PATH = Path(__file__).with_name("snapshots") / "extra_series.json"

# key → meta (ad, birim, kaynak, kategori, tanım, neden, alet) — yalnızca anlık görüntüde verisi olanlar gösterilir
DATASETS: dict[str, dict] = {
    "SEAICE_N": {
        "data_type": "satellite",
        "name_tr": "Arktik deniz buzu yayılımı", "name_en": "Arctic sea-ice extent", "unit": "milyon km²",
        "unit_en": "million km²", "category": "ice", "instrument": "NSIDC Sea Ice Index v4 (SSM/I · SSMIS uydu)",
        "source": "NSIDC Sea Ice Index v4 · Kuzey Yarımküre", "source_en": "NSIDC Sea Ice Index v4 · Northern Hemisphere",
        "definition_tr": "Kuzey Yarımküre'de en az %15 buzla kaplı deniz alanı (milyon km²); uydu mikrodalga ölçümü.",
        "definition_en": "Northern Hemisphere sea area at least 15% covered by ice (million km²); satellite microwave.",
        "why_tr": "Arktik, dünya ortalamasının yaklaşık dört katı hızla ısınıyor; yaz buzu hızla geriliyor.",
        "why_en": "The Arctic is warming about four times faster than the global mean; summer ice is retreating fast.",
        "regions": ("Grönland Buz Tabakası", "Alaska Permafrost Kuşağı", "Sibirya Taygası", "Kanada Kuzey Ormanları"),
        "bad_dir": "down",
    },
    "GPM": {
        "data_type": "satellite",
        "name_tr": "Uydu yağışı (GPM IMERG)", "name_en": "Satellite precipitation (GPM IMERG)", "unit": "mm/ay",
        "unit_en": "mm/month", "category": "water", "instrument": "NASA GPM IMERG V07 (aylık, 0,1°)",
        "source": "NASA GES DISC · GPM IMERG V07 aylık", "source_en": "NASA GES DISC · GPM IMERG V07 monthly",
        "definition_tr": "Uydu ağının (GPM çekirdek uydusu ve ortak mikrodalga/kızılötesi uydular) ölçtüğü aylık toplam "
                         "yağış; yer istasyonlarıyla düzeltilmiş.",
        "definition_en": "Monthly total precipitation measured by a satellite constellation (GPM core plus partner "
                         "microwave/infrared satellites), gauge-adjusted.",
        "why_tr": "Model yağışını (MERRA-2) bağımsız bir uydu ölçümüyle karşılaştırmayı sağlar.",
        "why_en": "Lets you compare model precipitation (MERRA-2) with an independent satellite measurement.",
        "regions": "all", "bad_dir": None,
    },
    "SEALEVEL": {
        "data_type": "insitu",
        "name_tr": "Deniz seviyesi (gelgit ölçer)", "name_en": "Sea level (tide gauge)", "unit": "mm",
        "unit_en": "mm", "category": "water", "instrument": "PSMSL gelgit ölçer (RLR aylık)",
        "source": "PSMSL · Permanent Service for Mean Sea Level (RLR aylık)",
        "source_en": "PSMSL · Permanent Service for Mean Sea Level (RLR monthly)",
        "definition_tr": "Kıyıdaki gelgit ölçerin kaydettiği aylık ortalama deniz seviyesi (mm, istasyonun kendi "
                         "referansına göre). Zemin çökmesi de dahil 'göreli' seviyedir.",
        "definition_en": "Monthly mean sea level recorded by a coastal tide gauge (mm, relative to the station's own "
                         "datum). It is 'relative' sea level, so land subsidence is included.",
        "why_tr": "Isınan okyanusun genleşmesi ve eriyen buzullar denizi yükseltir; çöken deltalarda etki katlanır.",
        "why_en": "Ocean thermal expansion and melting ice raise the sea; on sinking deltas the effect is amplified.",
        "regions": "psmsl", "bad_dir": "up",
    },
    "GLDAS_RUNOFF": {
        "data_type": "model",
        "name_tr": "Toplam akış (GLDAS)", "name_en": "Total runoff (GLDAS)", "unit": "mm/ay", "unit_en": "mm/month",
        "category": "water", "instrument": "NASA GLDAS-2.1 Noah (aylık, 0,25°)",
        "source": "NASA GES DISC · GLDAS-2.1 Noah aylık", "source_en": "NASA GES DISC · GLDAS-2.1 Noah monthly",
        "definition_tr": "Yüzeyden akan su ile topraktan derenlere sızan taban akışının aylık toplamı (mm); akarsulara "
                         "giden suyun ölçüsü.",
        "definition_en": "Monthly total of surface runoff plus subsurface baseflow (mm); a measure of water feeding "
                         "rivers.",
        "why_tr": "Yağış rejimi ve kar erimesi değiştikçe akarsuların beslenmesi de değişir; taşkın ve kuraklık "
                  "riskini doğrudan etkiler.",
        "why_en": "As rainfall regimes and snowmelt change, river supply changes too, directly affecting flood and "
                  "drought risk.",
        "regions": "all", "bad_dir": None,
    },
    "GLDAS_SOILDEEP": {
        "data_type": "model",
        "name_tr": "Derin toprak nemi 100–200 cm (GLDAS)", "name_en": "Deep soil moisture 100–200 cm (GLDAS)",
        "unit": "mm", "unit_en": "mm", "category": "soil", "instrument": "NASA GLDAS-2.1 Noah (aylık, 0,25°)",
        "source": "NASA GES DISC · GLDAS-2.1 Noah aylık", "source_en": "NASA GES DISC · GLDAS-2.1 Noah monthly",
        "definition_tr": "1–2 metre derinlikteki toprak katmanında tutulan su miktarı (kg/m² = mm).",
        "definition_en": "Water held in the soil layer 1–2 metres deep (kg/m² = mm).",
        "why_tr": "Derin katman yavaş tepki verir; uzun süreli kuraklığı ve yeraltı suyu baskısını yansıtır.",
        "why_en": "The deep layer responds slowly, reflecting long droughts and pressure on groundwater.",
        "regions": "all", "bad_dir": "down",
    },
    "GLDAS_SWE": {
        "data_type": "model",
        "name_tr": "Kar su eşdeğeri (GLDAS)", "name_en": "Snow water equivalent (GLDAS)", "unit": "mm", "unit_en": "mm",
        "category": "ice", "instrument": "NASA GLDAS-2.1 Noah (aylık, 0,25°)",
        "source": "NASA GES DISC · GLDAS-2.1 Noah aylık", "source_en": "NASA GES DISC · GLDAS-2.1 Noah monthly",
        "definition_tr": "Kar örtüsü eridiğinde açığa çıkacak suyun yüksekliği (mm).",
        "definition_en": "The depth of water the snowpack would yield if it melted (mm).",
        "why_tr": "Dağlardaki kar, yaz aylarında akarsuların su deposudur; azalması su kıtlığına yol açar.",
        "why_en": "Mountain snow is the summer water store for rivers; its decline leads to water scarcity.",
        "regions": "all", "bad_dir": "down",
    },
    "AIRS_T850": {
        "data_type": "satellite",
        "name_tr": "Alt atmosfer sıcaklığı 850 hPa (AIRS)", "name_en": "Lower-troposphere temperature 850 hPa (AIRS)", "unit": "°C", "unit_en": "°C", "category": "atmosphere",
        "instrument": "NASA AIRS v7 (Aqua uydusu, aylık, 1°)",
        "source": "NASA GES DISC · AIRS3STM v7 aylık · 850 hPa", "source_en": "NASA GES DISC · AIRS3STM v7 monthly · 850 hPa",
        "definition_tr": "Aqua uydusundaki AIRS kızılötesi sondajının ölçtüğü 850 hPa basınç seviyesindeki aylık ortalama hava sıcaklığı (gündüz geçişi).",
        "definition_en": "Monthly mean air temperature at the 850 hPa pressure level measured by the AIRS infrared sounder on Aqua (daytime pass).",
        "why_tr": "Yaklaşık 1,5 km yükseklik: yüzey etkilerinden arınmış troposfer ısınmasını gösterir.", "why_en": "About 1.5 km up: shows tropospheric warming free of surface effects.", "regions": "all", "bad_dir": "up",
    },
    "AIRS_T300": {
        "data_type": "satellite",
        "name_tr": "Üst troposfer sıcaklığı 300 hPa (AIRS)", "name_en": "Upper-troposphere temperature 300 hPa (AIRS)", "unit": "°C", "unit_en": "°C", "category": "atmosphere",
        "instrument": "NASA AIRS v7 (Aqua uydusu, aylık, 1°)",
        "source": "NASA GES DISC · AIRS3STM v7 aylık · 300 hPa", "source_en": "NASA GES DISC · AIRS3STM v7 monthly · 300 hPa",
        "definition_tr": "Aqua uydusundaki AIRS kızılötesi sondajının ölçtüğü 300 hPa basınç seviyesindeki aylık ortalama hava sıcaklığı (gündüz geçişi).",
        "definition_en": "Monthly mean air temperature at the 300 hPa pressure level measured by the AIRS infrared sounder on Aqua (daytime pass).",
        "why_tr": "Yaklaşık 9 km: tropiklerde üst troposferin yüzeyden hızlı ısınması beklenir.", "why_en": "About 9 km: in the tropics the upper troposphere is expected to warm faster than the surface.", "regions": "all", "bad_dir": "up",
    },
    "AIRS_T70": {
        "data_type": "satellite",
        "name_tr": "Alt stratosfer sıcaklığı 70 hPa (AIRS)", "name_en": "Lower-stratosphere temperature 70 hPa (AIRS)", "unit": "°C", "unit_en": "°C", "category": "atmosphere",
        "instrument": "NASA AIRS v7 (Aqua uydusu, aylık, 1°)",
        "source": "NASA GES DISC · AIRS3STM v7 aylık · 70 hPa", "source_en": "NASA GES DISC · AIRS3STM v7 monthly · 70 hPa",
        "definition_tr": "Aqua uydusundaki AIRS kızılötesi sondajının ölçtüğü 70 hPa basınç seviyesindeki aylık ortalama hava sıcaklığı (gündüz geçişi).",
        "definition_en": "Monthly mean air temperature at the 70 hPa pressure level measured by the AIRS infrared sounder on Aqua (daytime pass).",
        "why_tr": "Yaklaşık 18 km: sera gazları troposferi ısıtırken stratosferi soğutur; seviyeler arası zıt yönlü trendin klasik örneği.", "why_en": "About 18 km: greenhouse gases warm the troposphere but cool the stratosphere; the classic example of opposite trends between levels.", "regions": "all", "bad_dir": None,
    },
    "AIRS_O3": {
        "data_type": "satellite",
        "name_tr": "Toplam ozon (AIRS)", "name_en": "Total ozone (AIRS)", "unit": "DU", "unit_en": "DU",
        "category": "atmosphere", "instrument": "NASA AIRS v7 (Aqua uydusu, aylık, 1°)",
        "source": "NASA GES DISC · AIRS3STM v7 aylık", "source_en": "NASA GES DISC · AIRS3STM v7 monthly",
        "definition_tr": "Atmosfer sütunundaki toplam ozon miktarı (Dobson birimi); kızılötesi uydu ölçümü.",
        "definition_en": "Total ozone in the atmospheric column (Dobson units); infrared satellite measurement.",
        "why_tr": "Ozon tabakası Montreal Protokolü sonrası yavaşça toparlanıyor; kutuplarda mevsimsel incelme sürüyor.",
        "why_en": "The ozone layer is slowly recovering after the Montreal Protocol; seasonal polar thinning continues.",
        "regions": "all", "bad_dir": "down",
    },
    "OMI_NO2": {
        "data_type": "satellite",
        "name_tr": "Troposferik NO₂ (OMI)", "name_en": "Tropospheric NO₂ (OMI)", "unit": "10¹⁵ molekül/cm²",
        "unit_en": "10¹⁵ molecules/cm²", "category": "atmosphere", "instrument": "NASA OMI (Aura uydusu, günlük L3, 0,25°)",
        "source": "NASA GES DISC · OMI/Aura OMNO2d · ayda 4 gün örneklemi",
        "source_en": "NASA GES DISC · OMI/Aura OMNO2d · 4 days sampled per month",
        "definition_tr": "Yere yakın atmosferdeki azot dioksit miktarı (bulutsuz pikseller). Trafik, sanayi ve enerji "
                         "santrallerinin doğrudan izi.",
        "definition_en": "Nitrogen dioxide in the lower atmosphere (cloud-screened). A direct fingerprint of traffic, "
                         "industry and power plants.",
        "why_tr": "Hava kalitesi politikalarıyla azalır, hızlı sanayileşmeyle artar; aynı değişken ülkeden ülkeye zıt "
                  "yönde değişebilir.",
        "why_en": "Falls with clean-air policies and rises with rapid industrialisation; the same variable can trend "
                  "in opposite directions from country to country.",
        "regions": "all", "bad_dir": "up",
    },
    "MODIS_NDVI": {
        "data_type": "satellite",
        "name_tr": "Bitki örtüsü indeksi NDVI (MODIS)", "name_en": "Vegetation index NDVI (MODIS)", "unit": "NDVI",
        "unit_en": "NDVI", "category": "soil", "instrument": "NASA MODIS Terra MOD13C2 v061 (aylık, 0,05°)",
        "source": "NASA LP DAAC · MODIS MOD13C2 v061 aylık", "source_en": "NASA LP DAAC · MODIS MOD13C2 v061 monthly",
        "definition_tr": "Bitkilerin yeşilliğini gösteren indeks (−1…1; çöl ≈ 0,1, sık orman ≈ 0,8); uydunun kırmızı ve "
                         "yakın kızılötesi ölçümünden hesaplanır.",
        "definition_en": "An index of plant greenness (−1…1; desert ≈ 0.1, dense forest ≈ 0.8), computed from the "
                         "satellite's red and near-infrared measurements.",
        "why_tr": "Kuraklık ve çölleşmeyle azalır; ısınma ve CO₂ ile bazı bölgelerde \"yeşillenme\" görülür.",
        "why_en": "Falls with drought and desertification; warming and CO₂ cause \"greening\" in some regions.",
        "regions": "all", "bad_dir": "down",
    },
    "GRACE_TWS": {
        "data_type": "satellite",
        "name_tr": "Toplam su depolaması (GRACE/GRACE-FO)", "name_en": "Total water storage (GRACE/GRACE-FO)",
        "unit": "cm su", "unit_en": "cm water", "category": "water",
        "instrument": "NASA/DLR GRACE ve GRACE-FO uyduları (JPL mascon RL06.3)",
        "source": "NASA PO.DAAC · JPL GRACE/GRACE-FO mascon RL06.3 CRI",
        "source_en": "NASA PO.DAAC · JPL GRACE/GRACE-FO mascon RL06.3 CRI",
        "definition_tr": "İkiz uyduların aralarındaki mesafe değişiminden ölçülen yerçekimi farkı: bölgedeki toplam su "
                         "kütlesinin (yeraltı suyu, toprak suyu, kar ve buz) 2004–2009 ortalamasına göre değişimi, cm su "
                         "eşdeğeri. Bölgeler ~300 km çözünürlüktedir. Eksik aylar (pil yönetimi, 2017–2018 GRACE→GRACE-FO "
                         "geçişi) zaman içinde doğrusal ara değerle doldurulur.",
        "definition_en": "Gravity change measured from the distance between twin satellites: the change in total water "
                         "mass (groundwater, soil water, snow and ice) relative to 2004–2009, in cm of water. Resolution "
                         "is about 300 km. Missing months (battery management, the 2017–2018 GRACE→GRACE-FO gap) "
                         "are filled by linear interpolation in time.",
        "why_tr": "Yeraltı suyu tükenmesini ve buz tabakası kaybını doğrudan ölçen tek küresel yöntem (ör. İran, Hindistan "
                  "kuzeyi, Grönland).",
        "why_en": "The only global method that directly measures groundwater depletion and ice-sheet loss (e.g. Iran, "
                  "northern India, Greenland).",
        "regions": "all", "bad_dir": "down", "max_missing": 0.15, "interp": True,
    },
}


@st.cache_data(ttl=WEATHER_TTL, show_spinner=False)
def load_extra() -> dict:
    try:
        return json.loads(EXTRA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_extra(key: str, period: tuple[int, int], regions: dict[str, list], grid: list | None = None,
                meta: dict | None = None) -> Path:
    """Bir veri setini anlık görüntüye ekler/günceller (diğer veri setlerine dokunmaz)."""
    data = {}
    try:
        data = json.loads(EXTRA_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    data.setdefault("series", {})
    data["series"][key] = {"period": list(period), "regions": regions, "grid": grid, "meta": meta,
                           "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    data["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    EXTRA_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXTRA_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return EXTRA_PATH


# veri türü: jüri / öğrenci için "doğrudan ölçüm mü, model mi?" ayrımı (GLDAS bir kara yüzeyi modelidir, ölçüm değil)
DATA_TYPES = {
    "satellite": ("Uydu ölçümü", "Satellite"),
    "model": ("Model", "Model"),
    "insitu": ("Yerinde ölçüm", "In-situ"),
}


def data_type_label(key: str, lang: str = "tr") -> str:
    """Ek veri setinin tür etiketi: "Uydu ölçümü" / "Model (GLDAS)" / "Yerinde ölçüm (PSMSL)" (EN: Satellite / Model (GLDAS) / In-situ (PSMSL))."""
    m = DATASETS.get(key) or {}
    t = m.get("data_type", "satellite")
    tr, en = DATA_TYPES.get(t, DATA_TYPES["satellite"])
    label = en if lang == "en" else tr
    src = {"model": "GLDAS", "insitu": "PSMSL"}.get(t)
    return f"{label} ({src})" if src else label


def _rec(key: str, region: str) -> tuple[list | None, list[int] | None]:
    s = (load_extra().get("series") or {}).get(key)
    if not s:
        return None, None
    vals = (s.get("regions") or {}).get(region)
    return (vals, s["period"]) if vals else (None, None)


def extra_catalog(region: str, lang: str = "tr") -> list[dict]:
    """Bölge için mevcut ek veri setleri: [{key, name, unit, category, instrument, definition, why, source}]."""
    en = lang == "en"
    out = []
    for key, m in DATASETS.items():
        vals, _ = _rec(key, region)
        if vals is None or sum(v is None for v in vals) > len(vals) * m.get("max_missing", 0.1):
            continue
        out.append({"key": key, "name": m["name_en" if en else "name_tr"], "unit": m["unit_en" if en else "unit"],
                    "category": m["category"], "instrument": m["instrument"],
                    "definition": m["definition_en" if en else "definition_tr"], "why": m["why_en" if en else "why_tr"],
                    "source": m["source_en" if en else "source"], "bad_dir": m.get("bad_dir"),
                    "data_type": m.get("data_type", "satellite"), "type_label": data_type_label(key, lang)})
    return out


def extra_grid_annual(key: str) -> tuple[list | None, list[int] | None]:
    """Trend haritası için: 264 ızgara noktasının yıllık ortalamaları (en az 10 ayı olan yıllar), dönem yılları."""
    s = (load_extra().get("series") or {}).get(key)
    if not s or not s.get("grid"):
        return None, None
    y0, y1 = s["period"]
    years = list(range(y0, y1 + 1))
    out = []
    for vals in s["grid"]:
        ann = []
        need = 8 if DATASETS.get(key, {}).get("interp") else 10
        for k in range(len(years)):
            chunk = [v for v in vals[k * 12:(k + 1) * 12] if v is not None]
            ann.append(round(sum(chunk) / len(chunk), 4) if len(chunk) >= need else None)
        out.append(ann)
    return out, years


def _interp(vals: list) -> list:
    """Eksik ayları zaman içinde doğrusal ara değerle doldurur (uçlarda en yakın değer)."""
    idx = [i for i, v in enumerate(vals) if v is not None]
    if not idx:
        return vals
    out = list(vals)
    for i, v in enumerate(vals):
        if v is not None:
            continue
        lo = max((k for k in idx if k < i), default=None)
        hi = min((k for k in idx if k > i), default=None)
        if lo is None:
            out[i] = vals[hi]
        elif hi is None:
            out[i] = vals[lo]
        else:
            out[i] = round(vals[lo] + (vals[hi] - vals[lo]) * (i - lo) / (hi - lo), 3)
    return out


def extra_analysis(region: str, key: str) -> dict | None:
    """Ek veri setinin analizi — `variable_analysis` ile aynı şema (mk, sen, ttest, agree, years_to_significance,
    annual, chart, sentence_tr/en, source/source_en). Veri yoksa None."""
    from .variables import build_analysis

    m = DATASETS.get(key)
    spec = REGIONS.get(region)
    if m is None or spec is None:
        return None
    vals, period = _rec(key, region)
    if vals is None:
        return None
    y0, y1 = period
    dates = [f"{y}-{mm:02d}" for y in range(y0, y1 + 1) for mm in range(1, 13)]
    head = {"key": key, "name": m["name_tr"], "name_en": m["name_en"], "unit": m["unit"], "lat": spec.lat,
            "lon": spec.lon, "period": [y0, y1], "available": True, "reason": None, "reason_en": None, "live": True,
            "source": m["source"], "source_en": m["source_en"], "instrument": m["instrument"], "giovanni_url": None,
            "extra": True}
    missing = sum(v is None for v in vals)
    limit = m.get("max_missing", 0.1)
    if missing > len(vals) * limit:
        return {**head, "available": False, "reason": "Bu veri setinde dönemin %10'undan fazlası eksik.",
                "reason_en": "More than 10% of this dataset's period is missing."}
    if m.get("interp") and missing:
        vals = _interp(vals)
        head["filled_months"] = missing
    s = {"dates": dates, "values": vals, "y0": y0, "y1": y1, "unit": m["unit"], "lat": spec.lat, "lon": spec.lon}
    smeta = ((load_extra().get("series") or {}).get(key) or {}).get("meta") or {}
    st_ = smeta.get(region)
    if st_:
        head["station"] = st_
        head["source"] = f"{m['source']} · {st_['station']} ({st_['distance_km']} km)"
        head["source_en"] = f"{m['source_en']} · {st_['station']} ({st_['distance_km']} km)"
    out = build_analysis(head, s)
    if isinstance(out.get("chart"), dict):
        out["chart"]["title_tr"] = f"{m['name_tr']} · {m['instrument']}"
        out["chart"]["title_en"] = f"{m['name_en']} · {m['instrument']}"
    return out
