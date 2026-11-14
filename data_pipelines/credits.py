"""Veri kaynakları ve atıflar (Credits) — arayüzün "Credits" paneli için yapılandırılmış liste.

Frontend yalnızca `data_credits()` sonucunu gösterir; metinler burada (Backend) tutulur, böylece yeni bir veri
kaynağı eklendiğinde atıf da aynı yerde güncellenir. Her kayıt Türkçe ve İngilizce açıklama içerir.

Lisans/atıf notları kaynakların kendi kullanım koşullarından özetlenmiştir; resmî metin için `url` alanına bakın.
"""

from __future__ import annotations

from .real_series import KINDS, REAL_SOURCES, load_snapshot

# Kategori sırası arayüzde bölüm sırasıdır.
CATEGORIES = {
    "weather": ("Anlık ve tarihsel hava verisi", "Current & historical weather"),
    "climate": ("Uzun vadeli iklim ve tema serileri", "Long-term climate & theme series"),
    "ocean_ice": ("Okyanus, karbon ve deniz buzu", "Ocean, carbon & sea ice"),
    "events": ("Doğal olaylar", "Natural events"),
    "methods": ("Yöntem ve kaynakça", "Methods & references"),
    "ai": ("Yapay zekâ", "Artificial intelligence"),
    "software": ("Yazılım ve harita altlığı", "Software & base map"),
}

CREDITS: list[dict] = [
    # ── Hava ────────────────────────────────────────────────────────────────
    {
        "id": "meteomatics", "category": "weather", "name": "Meteomatics Weather API", "provider": "Meteomatics AG",
        "used_for_tr": "Canlı ve arşiv 2 m sıcaklık, deniz seviyesi basıncı, 10 m rüzgâr hızı/yönü, bağıl nem ve hava "
                       "sembolü (50 bölge + 15° küresel ızgara).",
        "used_for_en": "Live and archive 2 m temperature, mean sea-level pressure, 10 m wind speed/direction, relative "
                       "humidity and weather symbol (50 regions + 15° global grid).",
        "url": "https://www.meteomatics.com", "license": "Hackathon hesabı (NASA Space Apps Challenge 2026)",
        "attribution": "Weather data © Meteomatics AG",
    },
    {
        "id": "open-meteo", "category": "weather", "name": "Open-Meteo (Forecast & Historical Weather API)",
        "provider": "Open-Meteo.com",
        "used_for_tr": "Canlı termal anomali (son 30 gün), Meteomatics yedeği ve geçmiş tarihler için ERA5 arşivi "
                       "(anlık değerler ve termal sapma).",
        "used_for_en": "Live thermal anomaly (last 30 days), Meteomatics backup and ERA5 archive for historical dates.",
        "url": "https://open-meteo.com", "license": "CC BY 4.0",
        "attribution": "Weather data by Open-Meteo.com",
    },
    {
        "id": "era5", "category": "weather", "name": "ERA5 Reanalysis",
        "provider": "Copernicus Climate Change Service (C3S) / ECMWF",
        "used_for_tr": "Open-Meteo arşivi üzerinden geçmiş tarihlerin hava ve sıcaklık sapması verisi.",
        "used_for_en": "Historical weather and temperature-anomaly data via the Open-Meteo archive.",
        "url": "https://cds.climate.copernicus.eu", "license": "Copernicus lisansı (atıf zorunlu)",
        "attribution": "Contains modified Copernicus Climate Change Service information",
        "citation": "Hersbach, H. et al. (2020). The ERA5 global reanalysis. Q. J. R. Meteorol. Soc., 146, 1999–2049.",
    },
    # ── İklim ───────────────────────────────────────────────────────────────
    {
        "id": "nasa-power", "category": "climate", "name": "NASA POWER",
        "provider": "NASA Langley Research Center (LaRC)",
        "used_for_tr": "Bölge kartlarındaki uzun vadeli sıcaklık ve yağış trendi (Mann-Kendall) ile 27 bölgenin tema "
                       "serisi: sıcaklık, sıcaklık anomalisi, en yüksek sıcaklık, yağış, aerosol ve SPEI-3. Ayrıca "
                       "aylık iklim normalleri (kaynak yokken gösterilen değerler ve iklim normaline göre sapma).",
        "used_for_en": "Long-term temperature and precipitation trends on region cards, and the theme series of 27 "
                       "regions: temperature, anomaly, maximum temperature, precipitation, aerosol and SPEI-3; also "
                       "monthly climate normals (fallback values and deviation from normal).",
        "url": "https://power.larc.nasa.gov", "license": "Açık veri (NASA)",
        "attribution": "These data were obtained from the NASA Langley Research Center (LaRC) POWER Project funded "
                       "through the NASA Earth Science/Applied Science Program.",
    },
    {
        "id": "merra2", "category": "climate", "name": "MERRA-2", "provider": "NASA Global Modeling and Assimilation Office (GMAO)",
        "used_for_tr": "NASA POWER'ın sıcaklık, yağış ve aerosol (AOD 550 nm) verilerinin kaynağı olan yeniden analiz.",
        "used_for_en": "Reanalysis behind NASA POWER temperature, precipitation and aerosol (AOD 550 nm) data.",
        "url": "https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/", "license": "Açık veri (NASA)",
        "citation": "Gelaro, R. et al. (2017). The Modern-Era Retrospective Analysis for Research and Applications, "
                    "Version 2 (MERRA-2). J. Climate, 30, 5419–5454.",
    },
    # ── Okyanus, karbon, buz ────────────────────────────────────────────────
    {
        "id": "ersst", "category": "ocean_ice", "name": "NOAA ERSST v5 (ERDDAP üzerinden)",
        "provider": "NOAA National Centers for Environmental Information (NCEI) · NOAA CoastWatch ERDDAP",
        "used_for_tr": "Malakka Boğazı, Filipin Denizi, Büyük Set Resifi ve Humboldt Akıntısı deniz yüzeyi sıcaklığı.",
        "used_for_en": "Sea surface temperature for the Strait of Malacca, Philippine Sea, Great Barrier Reef and "
                       "Humboldt Current.",
        "url": "https://www.ncei.noaa.gov/products/extended-reconstructed-sst", "license": "Açık veri (NOAA)",
        "citation": "Huang, B. et al. (2017). Extended Reconstructed Sea Surface Temperature, Version 5 (ERSSTv5). "
                    "J. Climate, 30, 8179–8205.",
    },
    {
        "id": "noaa-gml-co2", "category": "ocean_ice", "name": "Mauna Loa CO₂ (aylık ortalama)",
        "provider": "NOAA Global Monitoring Laboratory (GML) · Scripps Institution of Oceanography",
        "used_for_tr": "Mauna Loa bölgesinin atmosferik CO₂ serisi.",
        "used_for_en": "Atmospheric CO₂ series of the Mauna Loa region.",
        "url": "https://gml.noaa.gov/ccgg/trends/", "license": "Açık veri (atıf istenir)",
        "attribution": "Dr. Xin Lan, NOAA/GML (gml.noaa.gov/ccgg/trends/) and Dr. Ralph Keeling, Scripps Institution "
                       "of Oceanography (scrippsco2.ucsd.edu/).",
    },
    {
        "id": "nsidc-sea-ice", "category": "ocean_ice", "name": "Sea Ice Index, Version 4 (G02135)",
        "provider": "National Snow and Ice Data Center (NSIDC)",
        "used_for_tr": "Antarktika Yarımadası bölgesinin Güney Yarımküre deniz buzu yayılımı serisi.",
        "used_for_en": "Southern Hemisphere sea-ice extent series of the Antarctic Peninsula region.",
        "url": "https://nsidc.org/data/g02135", "license": "Açık veri (atıf istenir)",
        "citation": "Fetterer, F. et al. Sea Ice Index, Version 4 (G02135). NSIDC, Boulder, Colorado USA.",
    },
    # ── Yapay zekâ ──────────────────────────────────────────────────────────
    {
        "id": "groq", "category": "ai", "name": "Groq API", "provider": "Groq, Inc.",
        "used_for_tr": "Seiron asistanının yanıtları (openai/gpt-oss-120b, yedek qwen/qwen3.8-27b). Anahtar yoksa yerel "
                       "kural tabanlı analiz motoru kullanılır.",
        "used_for_en": "Seiron assistant replies (openai/gpt-oss-120b, fallback qwen/qwen3.8-27b); a local rule-based "
                       "engine is used when no key is set.",
        "url": "https://groq.com", "license": "Groq kullanım koşulları",
    },
    # ── Yazılım ─────────────────────────────────────────────────────────────
    {
        "id": "natural-earth", "category": "software", "name": "Natural Earth (Plotly harita altlığı)",
        "provider": "Natural Earth",
        "used_for_tr": "3D kürenin kıyı çizgileri ve ülke sınırları.",
        "used_for_en": "Coastlines and country borders on the 3D globe.",
        "url": "https://www.naturalearthdata.com", "license": "Kamu malı (Public domain)",
    },
    {
        "id": "libraries", "category": "software", "name": "Açık kaynak kütüphaneler", "provider": "Topluluk",
        "used_for_tr": "Streamlit (arayüz), Plotly (küre ve grafikler), pandas · NumPy · SciPy (veri işleme), "
                       "pymannkendall (mevsimsel Mann-Kendall testi), qrcode · Pillow (QR kod), requests · truststore.",
        "used_for_en": "Streamlit (UI), Plotly (globe and charts), pandas · NumPy · SciPy (data processing), "
                       "pymannkendall (seasonal Mann-Kendall test), qrcode · Pillow (QR code), requests · truststore.",
        "url": "https://pypi.org", "license": "Apache 2.0 · MIT · BSD",
        "citation": "Hussain, Md. M. & Mahmud, I. (2019). pyMannKendall: a python package for non parametric Mann "
                    "Kendall family of trend tests. J. Open Source Software, 4(39), 1556.",
    },
    {
        "id": "fonts", "category": "software", "name": "Inter · Space Grotesk", "provider": "Google Fonts",
        "used_for_tr": "Arayüz yazı tipleri.", "used_for_en": "Interface typefaces.",
        "url": "https://fonts.google.com", "license": "SIL Open Font License 1.1",
    },
]

CREDITS.append({
    "id": "nasa-eonet", "category": "events", "name": "EONET v3 (Earth Observatory Natural Event Tracker)",
    "provider": "NASA Earth Science Data Systems",
    "used_for_tr": "Kürede isteğe bağlı gösterilen son 30 günün açık doğal olayları (orman yangını, şiddetli fırtına, "
                   "volkan, buz vb.; en fazla 150).",
    "used_for_en": "Open natural events of the last 30 days shown optionally on the globe (wildfires, severe storms, "
                   "volcanoes, ice etc.; up to 150).",
    "url": "https://eonet.gsfc.nasa.gov", "license": "Açık veri (NASA)",
    "attribution": "Natural event data: NASA Earth Observatory Natural Event Tracker (EONET).",
})

CREDITS.append({
    "id": "warming-stripes", "category": "climate", "name": "Warming Stripes (ısınma şeritleri) — görselleştirme fikri",
    "provider": "Ed Hawkins, University of Reading (#ShowYourStripes)",
    "used_for_tr": "Bölge panelindeki ısınma şeritleri görseli. Veriler VULPA'nın kendi NASA POWER yıllık ortalamalarıdır.",
    "used_for_en": "The warming-stripes graphic on the region panel. The data are VULPA's own NASA POWER annual means.",
    "url": "https://showyourstripes.info", "license": "CC BY 4.0",
    "attribution": "Warming stripes concept by Ed Hawkins (University of Reading), CC BY 4.0.",
})

# ── Büyük Plan (14.11.2026): değişken seçimi, nokta analizi, trend haritası, dedektif, yöntemler ─────────
CREDITS += [
    {
        "id": "nasa-power-monthly", "category": "climate", "name": "NASA POWER — aylık uç nokta (15 değişken)",
        "provider": "NASA Langley Research Center (LaRC) · MERRA-2 (GMAO)",
        "used_for_tr": "Değişken seçici ve nokta analizi (sıcaklık, en yüksek/düşük sıcaklık, yüzey sıcaklığı, yağış, "
                       "buharlaşma, bağıl/özgül nem, rüzgâr, bulutluluk, güneş ışınımı, aerosol, toprak nemi, kar "
                       "derinliği; 2001–2025), trend haritası (264 nokta) ve dedektif sihirbazı ön izlemeleri.",
        "used_for_en": "Variable picker and point analysis (temperature, max/min temperature, skin temperature, "
                       "precipitation, evaporation, relative/specific humidity, wind, cloud amount, solar radiation, "
                       "aerosol, soil moisture, snow depth; 2001–2025), the trend map (264 points) and detective previews.",
        "url": "https://power.larc.nasa.gov/docs/services/api/temporal/monthly/", "license": "Açık veri (NASA)",
        "attribution": "These data were obtained from the NASA Langley Research Center (LaRC) POWER Project funded "
                       "through the NASA Earth Science/Applied Science Program.",
    },
    {
        "id": "giovanni", "category": "software", "name": "NASA Giovanni", "provider": "NASA GES DISC",
        "used_for_tr": "Sonuçları bağımsız doğrulamak için grafiklerin altındaki \"NASA Giovanni'de doğrula\" "
                       "bağlantısı (MERRA-2 aylık, alan ortalamalı zaman serisi).",
        "used_for_en": "The \"Verify in NASA Giovanni\" link under charts for independent checking (MERRA-2 monthly, "
                       "area-averaged time series).",
        "url": "https://giovanni.gsfc.nasa.gov", "license": "Açık veri (NASA)",
        "attribution": "Analyses and visualizations used in this study were produced with the Giovanni online data "
                       "system, developed and maintained by the NASA GES DISC.",
    },
    {
        "id": "ref-mann-kendall", "category": "methods", "name": "Mevsimsel Mann-Kendall testi ve Sen eğimi",
        "provider": "Hirsch, Slack & Smith (1982) · Sen (1968)",
        "used_for_tr": "Eğilimin yönü ve anlamlılığı (mevsim döngüsü ayrı tutularak) ve aykırı değerlere dayanıklı "
                       "değişim hızı.",
        "used_for_en": "Trend direction and significance (with the seasonal cycle handled separately) and an "
                       "outlier-resistant rate of change.",
        "url": "https://doi.org/10.1029/WR018i001p00107", "license": "Bilimsel kaynak",
        "citation": "Hirsch, R. M., Slack, J. R. & Smith, R. A. (1982). Techniques of trend analysis for monthly water "
                    "quality data. Water Resources Research, 18(1), 107–121. · Sen, P. K. (1968). Estimates of the "
                    "regression coefficient based on Kendall's tau. JASA, 63(324), 1379–1389.",
    },
    {
        "id": "ref-gilbert", "category": "methods", "name": "Sen eğimi için %95 güven aralığı",
        "provider": "Gilbert (1987)",
        "used_for_tr": "Grafiklerdeki gölgeli güven aralığı bandı.", "used_for_en": "The shaded confidence band on charts.",
        "url": "https://www.osti.gov/biblio/7037501", "license": "Bilimsel kaynak",
        "citation": "Gilbert, R. O. (1987). Statistical Methods for Environmental Pollution Monitoring. Van Nostrand "
                    "Reinhold, New York.",
    },
    {
        "id": "ref-santer", "category": "methods", "name": "Otokorelasyon düzeltmeli t-testi",
        "provider": "Santer vd. (2000)",
        "used_for_tr": "Yöntem karşılaştırmasındaki t-testi (etkin örneklem sayısıyla).",
        "used_for_en": "The t-test in the method comparison (with effective sample size).",
        "url": "https://doi.org/10.1029/1999JD901105", "license": "Bilimsel kaynak",
        "citation": "Santer, B. D. et al. (2000). Statistical significance of trends and trend differences in "
                    "layer-average atmospheric temperature time series. J. Geophys. Res., 105(D6), 7337–7356.",
    },
    {
        "id": "ref-weatherhead", "category": "methods", "name": "Anlamlılık için gereken yıl sayısı",
        "provider": "Weatherhead vd. (1998)",
        "used_for_tr": "\"Bu eğilim aynı hızla sürerse kaç yıl daha veriyle anlamlı olur?\" tahmini.",
        "used_for_en": "The \"how many more years until significant\" estimate.",
        "url": "https://doi.org/10.1029/98JD00995", "license": "Bilimsel kaynak",
        "citation": "Weatherhead, E. C. et al. (1998). Factors affecting the detection of trends: statistical "
                    "considerations and applications to environmental data. J. Geophys. Res., 103(D14), 17149–17161.",
    },
    {
        "id": "ref-challenge", "category": "methods", "name": "NASA Space Apps Challenge 2026 — Be An Earth System Trend Detective",
        "provider": "NASA Earth Science Division",
        "used_for_tr": "Projenin yanıtladığı yarışma görevi.", "used_for_en": "The challenge this project responds to.",
        "url": "https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/",
        "license": "Yarışma görevi",
    },
]

# Lisans metinlerinin İngilizce karşılıkları (EN arayüz). "license" alanı Türkçe kalır (geriye uyumlu);
# her kayda "license_tr" ve "license_en" eklenir.
LICENSE_EN = {
    "meteomatics": "Hackathon account (NASA Space Apps Challenge 2026)",
    "open-meteo": "CC BY 4.0",
    "era5": "Copernicus licence (attribution required)",
    "nasa-power": "Open data (NASA)",
    "merra2": "Open data (NASA)",
    "ersst": "Open data (NOAA)",
    "noaa-gml-co2": "Open data (attribution requested)",
    "nsidc-sea-ice": "Open data (attribution requested)",
    "groq": "Groq terms of service",
    "natural-earth": "Public domain",
    "libraries": "Apache 2.0 · MIT · BSD",
    "fonts": "SIL Open Font License 1.1",
    "nasa-eonet": "Open data (NASA)",
    "warming-stripes": "CC BY 4.0",
    "nasa-power-monthly": "Open data (NASA)",
    "giovanni": "Open data (NASA)",
    "ref-mann-kendall": "Scientific reference", "ref-gilbert": "Scientific reference",
    "ref-santer": "Scientific reference", "ref-weatherhead": "Scientific reference",
    "ref-challenge": "Challenge statement",
}
for _c in CREDITS:
    _c["license_tr"] = _c["license"]
    _c["license_en"] = LICENSE_EN.get(_c["id"], _c["license"])

DISCLAIMER_TR = ("50 bölgenin {real}'ü gerçek ölçüm/yeniden analiz verisine dayanır. Kalan {synthetic} bölgenin tema "
                 "serisi (yangın hava indeksi, NDVI, deniz seviyesi, PM2.5, buzul alanı, yeraltı suyu, kar örtüsü) anahtarsız "
                 "ve uzun geçmişli bir kaynak bulunamadığı için sentetik prototip verisidir ve arayüzde böyle işaretlenir.")
DISCLAIMER_EN = ("{real} of the 50 regions use measured or reanalysis data. The theme series of the remaining {synthetic} "
                 "regions (fire weather index, NDVI, sea level, PM2.5, glacier area, groundwater, snow cover) are synthetic "
                 "prototype data because no key-free long-term source was found, and are labelled as such.")


def data_credits() -> dict:
    """Credits paneli için tüm içerik.

    Dönüş:
        {
          "categories": [{"id", "title_tr", "title_en", "items": [kayıt, ...]}, ...],
          "disclaimer_tr", "disclaimer_en",
          "real_regions": int, "synthetic_regions": int,
          "series_kinds": {tür: {"description", "source", "regions": int}},
          "snapshot_generated": "YYYY-MM-DD HH:MM UTC" | None,
        }
    Kayıt alanları: id, category, name, provider, used_for_tr, used_for_en, url, license (TR), license_tr,
    license_en, ve varsa attribution,
    citation.
    """
    real = len(REAL_SOURCES)
    kinds = {}
    for kind, (desc, src) in KINDS.items():
        kinds[kind] = {"description": desc, "source": src,
                       "regions": sum(1 for v in REAL_SOURCES.values() if v == kind)}
    return {
        "categories": [{"id": cid, "title_tr": tr, "title_en": en,
                        "items": [c for c in CREDITS if c["category"] == cid]}
                       for cid, (tr, en) in CATEGORIES.items()],
        "disclaimer_tr": DISCLAIMER_TR.format(real=real, synthetic=50 - real),
        "disclaimer_en": DISCLAIMER_EN.format(real=real, synthetic=50 - real),
        "real_regions": real, "synthetic_regions": 50 - real,
        "series_kinds": kinds,
        "snapshot_generated": load_snapshot().get("generated"),
    }
