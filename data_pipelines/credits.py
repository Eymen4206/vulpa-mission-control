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
                       "serisi: sıcaklık, sıcaklık anomalisi, en yüksek sıcaklık, yağış, aerosol ve SPEI-3.",
        "used_for_en": "Long-term temperature and precipitation trends on region cards, and the theme series of 27 "
                       "regions: temperature, anomaly, maximum temperature, precipitation, aerosol and SPEI-3.",
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
    Kayıt alanları: id, category, name, provider, used_for_tr, used_for_en, url, license, ve varsa attribution,
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
