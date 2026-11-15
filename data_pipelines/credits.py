"""Veri kaynakları ve atıflar (Credits) — arayüzün "Credits" paneli için yapılandırılmış liste.

Frontend yalnızca `data_credits()` sonucunu gösterir; metinler burada (Backend) tutulur, böylece yeni bir veri
kaynağı eklendiğinde atıf da aynı yerde güncellenir. Her kayıt Türkçe ve İngilizce açıklama içerir.

Lisans/atıf notları kaynakların kendi kullanım koşullarından özetlenmiştir; resmî metin için `url` alanına bakın.
"""

from __future__ import annotations

from .real_series import KINDS, REAL_SOURCES, load_snapshot
from .regions import REGION_LIST

# Kategori sırası arayüzde bölüm sırasıdır.
CATEGORIES = {
    "weather": ("Anlık ve tarihsel hava verisi", "Current & historical weather"),
    "climate": ("Uzun vadeli iklim ve tema serileri", "Long-term climate & theme series"),
    "ocean_ice": ("Okyanus, karbon ve deniz buzu", "Ocean, carbon & sea ice"),
    "events": ("Doğal olaylar", "Natural events"),
    "satellite": ("Uydu ve yer ölçümleri", "Satellite & in-situ measurements"),
    "methods": ("Yöntem ve kaynakça", "Methods & references"),
    "ai": ("Yapay zekâ", "Artificial intelligence"),
    "software": ("Yazılım ve harita altlığı", "Software & base map"),
}

_N = len(REGION_LIST)   # bölge sayısı (metinlerde sabit "50" yerine)

CREDITS: list[dict] = [
    # ── Hava ────────────────────────────────────────────────────────────────
    {
        "id": "meteomatics", "category": "weather", "name": "Meteomatics Weather API", "provider": "Meteomatics AG",
        "used_for_tr": "Canlı ve arşiv 2 m sıcaklık, deniz seviyesi basıncı, 10 m rüzgâr hızı/yönü, bağıl nem ve hava "
                       f"sembolü ({_N} bölge + 15° küresel ızgara).",
        "used_for_en": "Live and archive 2 m temperature, mean sea-level pressure, 10 m wind speed/direction, relative "
                       f"humidity and weather symbol ({_N} regions + 15° global grid).",
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
        "used_for_tr": "Bölge kartlarındaki uzun vadeli sıcaklık ve yağış trendi (Mann-Kendall) ile 39 bölgenin tema "
                       "serisi: sıcaklık, sıcaklık anomalisi, en yüksek sıcaklık, yağış, aerosol, SPEI-3, toprak nemi "
                       "ve kar derinliği. Ayrıca "
                       "aylık iklim normalleri (kaynak yokken gösterilen değerler ve iklim normaline göre sapma).",
        "used_for_en": "Long-term temperature and precipitation trends on region cards, and the theme series of 39 "
                       "regions: temperature, anomaly, maximum temperature, precipitation, aerosol, SPEI-3, soil "
                       "moisture and snow depth; also "
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
        "used_for_tr": "9 kıyı ve deniz bölgesinin deniz yüzeyi sıcaklığı: Malakka Boğazı, Filipin Denizi, Büyük Set "
                       "Resifi, Humboldt Akıntısı, Nijer Deltası, Yangtze Deltası, Cava Kuzey Kıyısı, ABD Doğu Kıyısı, "
                       "Florida Everglades.",
        "used_for_en": "Sea surface temperature for 9 coastal and ocean regions: Strait of Malacca, Philippine Sea, "
                       "Great Barrier Reef, Humboldt Current, Niger Delta, Yangtze Delta, North Java Coast, US East "
                       "Coast, Florida Everglades.",
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
        "used_for_tr": "Antarktika Yarımadası bölgesinin Güney Yarımküre deniz buzu yayılımı serisi ve Grönland, "
                       "Alaska, Sibirya ve Kanada için Arktik (Kuzey Yarımküre) deniz buzu yayılımı.",
        "used_for_en": "Southern Hemisphere sea-ice extent for the Antarctic Peninsula region and Arctic (Northern "
                       "Hemisphere) sea-ice extent for Greenland, Alaska, Siberia and Canada.",
        "url": "https://nsidc.org/data/g02135", "license": "Açık veri (atıf istenir)",
        "citation": "Fetterer, F. et al. Sea Ice Index, Version 4 (G02135). NSIDC, Boulder, Colorado USA.",
    },
    # ── Yapay zekâ ──────────────────────────────────────────────────────────
    {
        "id": "groq", "category": "ai", "name": "Groq API", "provider": "Groq, Inc.",
        "used_for_tr": "Seiron asistanının yanıtları (openai/gpt-oss-120b; yedekler qwen/qwen3.8-27b ve openai/gpt-oss-20b). Anahtar yoksa yerel "
                       "kural tabanlı analiz motoru kullanılır.",
        "used_for_en": "Seiron assistant replies (openai/gpt-oss-120b; fallbacks qwen/qwen3.8-27b and openai/gpt-oss-20b); a local rule-based "
                       "engine is used when no key is set.",
        "url": "https://groq.com", "license": "Groq kullanım koşulları",
    },
    {
        "id": "claude", "category": "ai", "name": "Claude · Claude Code", "provider": "Anthropic",
        "used_for_tr": "Süper zekâ (SI) desteği: kodun yazılması ve hata ayıklama, arayüz metinleri ve TR ↔ EN çeviri, "
                       "veri kaynaklarının ve yöntemlerin araştırılması, VULPA kurt logosu, jüri videosu ve müziği "
                       "(kodla üretildi). Tüm sonuçlar ekip tarafından gözden geçirildi; analizler NASA verisiyle hesaplanır.",
        "used_for_en": "Super Intelligence (SI) assistance: writing and debugging the code, interface text and TR ↔ EN "
                       "translation, researching data sources and methods, the VULPA wolf logo, the jury video and its "
                       "music (generated with code). All output was reviewed by the team; analyses are computed from "
                       "NASA data.",
        "url": "https://www.anthropic.com/claude", "license": "Anthropic kullanım koşulları",
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

# ── Ek ölçüm veri setleri (satellite.py) ────────────────────────────────────
def _sat(id_, name, provider, tr, en, url, citation=None, attribution=None):
    d = {"id": id_, "category": "satellite", "name": name, "provider": provider, "used_for_tr": tr, "used_for_en": en,
         "url": url, "license": "Açık veri (NASA)"}
    if citation:
        d["citation"] = citation
    if attribution:
        d["attribution"] = attribution
    return d


CREDITS += [
    _sat("gpm-imerg", "GPM IMERG V07 (aylık)", "NASA GES DISC · GPM",
         f"Uydu yağışı: {_N} bölge ve trend haritası (2001–2025); model yağışıyla karşılaştırma.",
         f"Satellite precipitation: {_N} regions and the trend map (2001–2025); comparison with model precipitation.",
         "https://gpm.nasa.gov/data/imerg",
         "Huffman, G. J. et al. (2023). GPM IMERG Final Precipitation L3 1 month 0.1 degree x 0.1 degree V07, GES DISC, "
         "doi:10.5067/GPM/IMERG/3B-MONTH/07."),
    _sat("gldas", "GLDAS-2.1 Noah (aylık)", "NASA GES DISC · GLDAS",
         "Toplam akış (yüzey + taban), 100–200 cm toprak nemi ve kar su eşdeğeri.",
         "Total runoff (surface + baseflow), 100–200 cm soil moisture and snow water equivalent.",
         "https://ldas.gsfc.nasa.gov/gldas",
         "Beaudoing, H. & Rodell, M. (2020). GLDAS Noah Land Surface Model L4 monthly 0.25 x 0.25 degree V2.1, GES DISC, "
         "doi:10.5067/SXAVCZFAQLNO."),
    _sat("airs", "AIRS v7 L3 aylık (Aqua)", "NASA GES DISC · AIRS",
         "850 / 300 / 70 hPa sıcaklıkları (atmosfer katmanları) ve toplam ozon.",
         "Temperature at 850 / 300 / 70 hPa (atmospheric levels) and total ozone.",
         "https://airs.jpl.nasa.gov",
         "AIRS Project (2019). Aqua/AIRS L3 Monthly Standard Physical Retrieval (AIRS-only) 1 degree x 1 degree V7.0, "
         "GES DISC, doi:10.5067/UBENJB9D3T2H."),
    _sat("omi-no2", "OMI/Aura OMNO2d (günlük L3)", "NASA GES DISC · OMI",
         "Troposferik NO₂ (bulut elemeli), ayda 4 gün örneklemiyle aylık ortalama (2005–2024).",
         "Tropospheric NO₂ (cloud-screened), monthly mean from 4 sampled days per month (2005–2024).",
         "https://aura.gsfc.nasa.gov/omi.html",
         "Krotkov, N. A. et al. (2019). OMI/Aura NO2 Tropospheric, Stratospheric & Total Columns MINDS Daily L3, "
         "GES DISC (OMNO2d v003)."),
    _sat("modis-ndvi", "MODIS Terra MOD13C2 v061 (aylık NDVI)", "NASA LP DAAC · MODIS",
         f"Bitki örtüsü indeksi (NDVI): {_N} bölge ve trend haritası.", f"Vegetation index (NDVI): {_N} regions and the trend map.",
         "https://lpdaac.usgs.gov/products/mod13c2v061/",
         "Didan, K. (2021). MODIS/Terra Vegetation Indices Monthly L3 Global 0.05Deg CMG V061, NASA LP DAAC, "
         "doi:10.5067/MODIS/MOD13C2.061."),
    _sat("grace", "GRACE / GRACE-FO JPL mascon RL06.3 CRI", "NASA JPL · PO.DAAC (NASA/DLR · NASA/GFZ)",
         f"Toplam su depolaması (yeraltı suyu, toprak suyu, kar, buz): {_N} bölge ve trend haritası (2003–2024).",
         f"Total water storage (groundwater, soil water, snow, ice): {_N} regions and the trend map (2003–2024).",
         "https://grace.jpl.nasa.gov",
         "Watkins, M. M. et al. (2015). Improved methods for observing Earth's time variable mass distribution with "
         "GRACE using spherical cap mascons. J. Geophys. Res. Solid Earth, 120, 2648–2671. · Wiese, D. N. et al. "
         "(2023). JPL GRACE and GRACE-FO Mascon Ocean, Ice, and Hydrology Equivalent Water Height CRI Filtered RL06.3 "
         "V4, PO.DAAC."),
    {"id": "psmsl", "category": "satellite", "name": "PSMSL — Permanent Service for Mean Sea Level (RLR aylık)",
     "provider": "National Oceanography Centre, Liverpool",
     "used_for_tr": "Gelgit ölçerlerden göreli deniz seviyesi: ABD Doğu Kıyısı (Lewisetta), Florida (Virginia Key), "
                    "Chao Phraya (Bangkok), Yangtze (Kanmen); 2000–2024.",
     "used_for_en": "Relative sea level from tide gauges: US East Coast (Lewisetta), Florida (Virginia Key), Chao Phraya "
                    "(Bangkok), Yangtze (Kanmen); 2000–2024.",
     "url": "https://psmsl.org", "license": "Açık veri (atıf gerekli)",
     "citation": "Holgate, S. J. et al. (2013). New Data Systems and Products at the Permanent Service for Mean Sea "
                 "Level. Journal of Coastal Research, 29(3), 493–504."},
    {"id": "earthdata", "category": "satellite", "name": "NASA Earthdata (GES DISC · LP DAAC · Earthdata Cloud OPeNDAP)",
     "provider": "NASA Earth Science Data Systems",
     "used_for_tr": "Uydu verilerine erişim. Veriler bir kez çekilip depoya kaydedilir; canlı site token kullanmaz.",
     "used_for_en": "Access to the satellite data. Data are fetched once and stored in the repository; the live site "
                    "uses no token.",
     "url": "https://www.earthdata.nasa.gov", "license": "Açık veri (NASA)"},
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
    "claude": "Anthropic terms of service",
    "natural-earth": "Public domain",
    "libraries": "Apache 2.0 · MIT · BSD",
    "fonts": "SIL Open Font License 1.1",
    "nasa-eonet": "Open data (NASA)",
    "warming-stripes": "CC BY 4.0",
    "gpm-imerg": "Open data (NASA)", "gldas": "Open data (NASA)", "airs": "Open data (NASA)",
    "omi-no2": "Open data (NASA)", "modis-ndvi": "Open data (NASA)", "earthdata": "Open data (NASA)",
    "psmsl": "Open data (attribution required)", "grace": "Open data (NASA)",
    "nasa-power-monthly": "Open data (NASA)",
    "giovanni": "Open data (NASA)",
    "ref-mann-kendall": "Scientific reference", "ref-gilbert": "Scientific reference",
    "ref-santer": "Scientific reference", "ref-weatherhead": "Scientific reference",
    "ref-challenge": "Challenge statement",
}
# Kayıt adlarının İngilizcesi (EN arayüzde Türkçe ad kalıyordu; jüri videosu kaydında görüldü). "name" Türkçe kalır.
NAME_EN = {
    "ersst": "NOAA ERSST v5 (via ERDDAP)",
    "noaa-gml-co2": "Mauna Loa CO₂ (monthly mean)",
    "natural-earth": "Natural Earth (Plotly base map)",
    "libraries": "Open-source libraries",
    "warming-stripes": "Warming Stripes — visualisation concept",
    "nasa-power-monthly": "NASA POWER — monthly endpoint (15 variables)",
    "ref-mann-kendall": "Seasonal Mann-Kendall test and Sen slope",
    "ref-gilbert": "95% confidence interval for the Sen slope",
    "ref-santer": "Autocorrelation-corrected t-test",
    "ref-weatherhead": "Years needed for significance",
    "psmsl": "PSMSL — Permanent Service for Mean Sea Level (RLR monthly)",
    "gpm-imerg": "GPM IMERG V07 (monthly)",
    "gldas": "GLDAS-2.1 Noah (monthly)",
    "airs": "AIRS v7 L3 monthly (Aqua)",
    "omi-no2": "OMI/Aura OMNO2d (daily L3)",
    "modis-ndvi": "MODIS Terra MOD13C2 v061 (monthly NDVI)",
}
PROVIDER_EN = {"libraries": "Community"}
for _c in CREDITS:
    _c["license_tr"] = _c["license"]
    _c["license_en"] = LICENSE_EN.get(_c["id"], _c["license"])
    _c["name_tr"], _c["name_en"] = _c["name"], NAME_EN.get(_c["id"], _c["name"])
    _c["provider_en"] = PROVIDER_EN.get(_c["id"], _c["provider"])

DISCLAIMER_TR = ("{n} bölgenin {real}'ü gerçek ölçüm/yeniden analiz verisine dayanır. Kalan {synthetic} bölgenin tema "
                 "serisi (yangın hava indeksi, NDVI, deniz seviyesi, PM2.5, buzul alanı, yeraltı suyu, kar örtüsü) anahtarsız "
                 "ve uzun geçmişli bir kaynak bulunamadığı için sentetik prototip verisidir ve arayüzde böyle işaretlenir.")
DISCLAIMER_EN = ("{real} of the {n} regions use measured or reanalysis data. The theme series of the remaining {synthetic} "
                 "regions (fire weather index, NDVI, sea level, PM2.5, glacier area, groundwater, snow cover) are synthetic "
                 "prototype data because no key-free long-term source was found, and are labelled as such.")

# 14.11.2026: tüm bölgelerin tema serisi gerçek veriye dayanıyor ({n} = bölge sayısı).
DISCLAIMER_ALL_TR = ("{n} bölgenin tamamının tema serisi gerçek ölçüm ya da yeniden analiz verisidir (NASA POWER/MERRA-2, "
                     "NOAA ERSST, NOAA GML, NSIDC). Bazı temalarda (yangın riski, deniz seviyesi, partikül kirliliği, "
                     "çölleşme, buzul) doğrudan ölçüm anahtarsız bulunamadığından ilgili fiziksel bir değişken "
                     "kullanılır; değişken adı ölçülen şeyi açıkça söyler (ör. PM2.5 yerine aerosol optik derinliği).")
DISCLAIMER_ALL_EN = ("The theme series of all {n} regions are measured or reanalysis data (NASA POWER/MERRA-2, NOAA ERSST, "
                     "NOAA GML, NSIDC). For some themes (fire risk, sea level, particulate pollution, desertification, "
                     "glaciers) no key-free direct measurement exists, so a related physical variable is used; the "
                     "variable name states exactly what is measured (e.g. aerosol optical depth instead of PM2.5).")


# Proje sahipleri (Credits başlığında gösterilir).
TEAM = ("Mete", "Yahya", "Eymen")

# Süper zekâ (SI) kullanım beyanı — NASA Space Apps kuralı: SI kullanımı açıkça belirtilmeli.
SI_NOTE_TR = ("Süper zekâ (SI) beyanı: Bu projede Claude / Claude Code (Anthropic) kod, metin, çeviri, araştırma, logo, "
              "video ve müzik için; Seiron asistanında Groq üzerinden büyük dil modelleri kullanıldı. NASA logosu ya da "
              "marka öğesi SI ile üretilmedi ve kullanılmadı.")
SI_NOTE_EN = ("Super Intelligence (SI) disclosure: Claude / Claude Code (Anthropic) was used for code, text, translation, "
              "research, the logo, the video and its music; the Seiron assistant uses large language models via Groq. "
              "No NASA logo or branding element was generated with SI or used.")


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
        "disclaimer_tr": (DISCLAIMER_ALL_TR.format(n=_N) if real >= _N
                          else DISCLAIMER_TR.format(n=_N, real=real, synthetic=_N - real)),
        "disclaimer_en": (DISCLAIMER_ALL_EN.format(n=_N) if real >= _N
                          else DISCLAIMER_EN.format(n=_N, real=real, synthetic=_N - real)),
        "team": list(TEAM), "si_note_tr": SI_NOTE_TR, "si_note_en": SI_NOTE_EN,
        "real_regions": real, "synthetic_regions": _N - real,
        "series_kinds": kinds,
        "snapshot_generated": load_snapshot().get("generated"),
    }
