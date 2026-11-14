# data_pipelines/ — VULPA veri katmanı

**Sahibi:** 2. yapay zekâ asistanı (Backend / veri çekme).
**Frontend asistanı bu klasöre yazmaz.** Frontend `app.py` ve `components/` dosyalarından sorumludur.

## Görev sınırı

| Alan | Sorumlu | Klasör / dosya |
|---|---|---|
| Veri çekme, API'ler, önbellek, istatistik | 2. asistan | `data_pipelines/` |
| Arayüz, düzen, küre, Seiron paneli | Frontend asistanı | `app.py`, `components/` |

## Durum: veri kodu buraya kopyalandı (2026-11-14)

Aşağıdaki fonksiyonlar `app.py` içinden **kopyalandı** (app.py'den hiçbir şey silinmedi). Ad, parametre ve
dönüş yapıları birebir aynıdır; gövdeler AST karşılaştırmasıyla doğrulandı. Frontend, `app.py` içindeki
tanımları silip aşağıdaki `import` satırıyla bu paketi kullanabilir.

### Modüller

| Modül | İçerik |
|---|---|
| `regions.py` | `Region`, `REGION_LIST`, `REGIONS`, `CITY_NAMES` |
| `config.py` | Sabitler (`START`, `END`, `PERIOD`, `WEATHER_TTL`, `MM_*`, `POWER_URL`, `GRID_*`, `NOW` …) ve `hist_date(year)` |
| `weather.py` | Meteomatics + Open-Meteo, 50 bölge hava verisi |
| `grid.py` | 15° küresel ızgara (ham numpy alanları) |
| `power.py` | NASA POWER uzun vadeli trend |
| `series.py` | `build_series`, `analyze` |

### `data_pipelines/__init__.py` içinden dışa aktarılanlar (`__all__`)

| Grup | Adlar |
|---|---|
| Bölgeler | `Region`, `REGION_LIST`, `REGIONS`, `CITY_NAMES` |
| Meteomatics | `meteomatics_auth`, `meteomatics_now`, `meteomatics_daily_anomaly`, `mm_time` |
| 50 bölge hava verisi | `_fetch_live_weather`, `_fetch_historical_weather`, `_fetch_weather`, `_fallback_weather`, `_open_meteo_cities`, `_merge_mm`, `describe_code`, `describe_symbol`, `WEATHER_CODES`, `MM_SYMBOLS` |
| Küresel ızgara | `_fetch_live_grid`, `_fetch_historical_grid`, `_fetch_grid`, `_fallback_grid` |
| NASA POWER | `_fetch_power`, `_power_simulated` |
| Sentetik seri / istatistik | `build_series`, `analyze` |
| Sabitler ve zaman | `START`, `END`, `PERIOD`, `PROJECTION_MONTHS`, `NOW`, `LAST_FULL_YEAR`, `POWER_SPAN`, `WEATHER_TTL`, `MM_URL`, `MM_CORE`, `MM_EXTRA`, `POWER_URL`, `GRID_STEP`, `GRID_LATS`, `GRID_LONS`, `hist_date` |

Örnek içe aktarma (Frontend için):

```python
from data_pipelines import (
    Region, REGION_LIST, REGIONS, CITY_NAMES,
    meteomatics_auth, meteomatics_now, meteomatics_daily_anomaly,
    _fetch_weather, _fetch_live_weather, _fetch_historical_weather,
    _fetch_grid, _fetch_live_grid, _fetch_historical_grid,
    _fetch_power, build_series, analyze,
)
```

### Bilinçli olarak app.py'de bırakılanlar

- **Görselleştirme:** `grid_layers`, `_resample`, `_contour_segments`, `_wrap_cols`, `blend`, `*_STOPS`, `sparkline`.
- **Dil ve metin:** `L`, `lang`, `rname`, `rarea`, `rtheme`, `rvar`, `compass`, `wlabel`, `when_text`, `weather_sentence`, `power_sentence`, `VAR_EN`, `WEATHER_EN`.
- **Oturum durumunu okuyan sarmalayıcılar:** `sel_year`, `fetch_weather`, `fetch_grid`, `fetch_power`, `power_window`, `current_grid`, `weather_of`, `weather_extremes`. Bunlar `st.session_state` okur ve aşağıdaki veri fonksiyonlarını çağırır.
- **Diğer:** `export_csv`. `build_series` üzerine kurulu bir indirme yardımcısıdır; istenirse buraya da eklenebilir.

### Notlar

- `build_series` ve `analyze` app.py'de TTL'siz `@st.cache_data` ile tanımlıydı. Burada kurala uygun olarak
  `ttl=1800` verildi. Çıktıları deterministik olduğu için sonuç değişmez.
- `NOW` (ve dolayısıyla `LAST_FULL_YEAR`, `hist_date`) modül yüklendiği anda hesaplanır, app.py ile aynı davranış.

## Fonksiyon özeti

| Fonksiyon | Ne yapar | Dönüş |
|---|---|---|
| `meteomatics_auth()` | `st.secrets["meteomatics"]` → HTTPBasicAuth | `HTTPBasicAuth \| None` |
| `meteomatics_now(params, locations, timeout, when)` | Meteomatics anlık/arşiv sorgusu | `({param: {(lat, lon): değer}}, "SS:DD")` |
| `meteomatics_daily_anomaly(locations, day)` | 30 günlük sıcaklık sapması | `{(lat, lon): °C}` |
| `_fetch_live_weather()` / `_fetch_historical_weather(year)` | 50 bölge hava verisi | `{"live", "time", "data", "source", "provider", "anomaly_live", "year"}` |
| `_fetch_live_grid()` / `_fetch_historical_grid(year)` | 15° küresel ızgara | `{"live", "time", "source", "temp", "anomaly", "pressure", "wind", "wind_dir"}` (numpy 11×24) |
| `_fetch_power(city, y0, y1)` | NASA POWER günlük → aylık, Mann-Kendall | trend sözlüğü (`t_dec`, `t_p`, `annual_t`, `y0`, `y1` …) |
| `build_series(region)` / `analyze(region)` | Sentetik tema serisi ve mevsimsel Mann-Kendall | `DataFrame` / istatistik sözlüğü |

Kurallar:
- Hepsi `@st.cache_data(ttl=1800)` ile önbelleklenir; ağ ya da kimlik doğrulama hatasında **istisna fırlatmaz**,
  simülasyon yedeğine geçer.
- Gizli bilgiler (Meteomatics, Groq) yalnızca `.streamlit/secrets.toml` üzerinden okunur; koda yazılmaz.

---

## Yıl aralığı ve fark (delta) desteği — 14.11.2026 (Backend · Msi-nb)

Frontend'in tek yıl seçicisini "Yıl Aralığı" (`start_year`, `end_year`) seçicisine çevirmesi için eklendi.
**Geriye uyumludur:** mevcut tek yıllı çağrılar (`_fetch_weather(year)`, `_fetch_grid(year)`) aynen çalışır.
Frontend istediği zaman iki parametreli çağrıya geçebilir.

### Değişen imzalar

| Fonksiyon | Eski | Yeni |
|---|---|---|
| `_fetch_weather` | `(year)` | `(start_year=0, end_year=None)`. `end_year` verilmezse eski davranış. |
| `_fetch_grid` | `(year)` | `(start_year=0, end_year=None)`. `end_year` verilmezse eski davranış. |
| `_fetch_power` | `(city, y0, y1)` | Aynı imza; `y0` = başlangıç, `y1` = bitiş yılı. Pencere artık sıralanıp 1981 ile son tamamlanmış yıl arasına çekilir. |

Yeni dışa aktarılanlar: `_fetch_weather_range`, `_fetch_grid_range`, `range_year`, `DELTA_FIELDS`, `power_years`,
`POWER_FIRST_YEAR`, `MIN_TREND_YEARS`.

### `_fetch_weather(start_year, end_year)` dönüşü

Bitiş yılının normal sözlüğü (`live`, `time`, `data`, `provider`, `anomaly_live`) ve ek olarak:

| Anahtar | Anlamı |
|---|---|
| `range` | `True` (aralık modu) |
| `start_year`, `end_year` | Kullanılan yıllar (0 verildiyse bu yıl) |
| `start_time`, `end_time` | `"GG.AA.YYYY 12:00"` |
| `start_live`, `end_live`, `delta_live` | Uçların gerçek veri olup olmadığı; `delta_live` = ikisi de gerçek |
| `delta_summary` | `{"temp"\|"pressure"\|"wind": {"mean", "max_region", "max", "min_region", "min"}}` |
| `source` | ör. `"Meteomatics · 14.11.2010 12:00 → 14.11.2025 12:00 UTC"`; simülasyon varsa bunu açıkça yazar |
| `year` | `end_year` (eski tek yıllı kodla uyum için) |

`data[bölge]` içine eklenen anahtarlar (birimler: °C, hPa, km/sa):

| Anahtar | Anlamı |
|---|---|
| `temp`, `pressure`, `wind` | Bitiş yılı değeri (eskisi gibi) |
| `temp_start`, `pressure_start`, `wind_start` | Başlangıç yılı değeri |
| `temp_delta`, `pressure_delta`, `wind_delta` | Bitiş − başlangıç (2 ondalık); bir uç eksikse `None` |

### `_fetch_grid(start_year, end_year)` dönüşü

Bitiş yılının ızgarası ve ek olarak `temp_delta`, `pressure_delta`, `wind_delta`, `temp_start`, `pressure_start`,
`wind_start` (numpy 11×24), `range`, `start_year`, `end_year`, `start_time`, `end_time`, `start_live`, `end_live`,
`delta_live`.

### `_fetch_power(city, start_year, end_year)` ek anahtarları

| Anahtar | Anlamı |
|---|---|
| `start_year`, `end_year` | Düzeltilmiş pencere (`y0`, `y1` ile aynı) |
| `n_years`, `short_window` | Pencere uzunluğu; 3 yıldan kısaysa `True` ve eğilim testi yapılmaz (`t_trend="no trend"`, `t_p=1.0`, eğim 0) |
| `first_t`, `first_prec` | Başlangıç yılının yıllık ortalama sıcaklığı ve toplam yağışı |
| `t_delta`, `prec_delta` | Bitiş − başlangıç yılı (°C, mm) |

Mann-Kendall ve Sen eğimi (`t_dec`, `t_p`, `p_dec` …) yalnızca seçilen pencere için hesaplanır.

### Frontend için önemli notlar

- **0 = canlı:** Aralık modunda 0 "bu yıl" sayılır ve canlı sorgu yerine bugünün 12:00 UTC verisi kullanılır.
  Böylece iki uç aynı saatte karşılaştırılır; gün içi sıcaklık döngüsü farka karışmaz.
- **Tek günlük fark iklim eğilimi değildir.** `temp_delta`, iki yılın *aynı günündeki* hava durumu farkıdır ve
  hava değişkenliği nedeniyle ±15 °C olabilir (ör. Sibirya). Arayüzde bunu "iklim değişimi" olarak sunmayın;
  iklimsel değişim için `_fetch_power` sonucundaki `t_dec` (Mann-Kendall eğimi) ve `t_delta` kullanılmalı.
- **Etiketleme:** `delta_live` False ise arayüz "tahmini" etiketi göstermeli; `source` metni bunu zaten içerir.
- **Süre:** Bir aralık çağrısı iki arşiv sorgusu yapar (ilk çağrı ≈4–9 sn, sonra 30 dk önbellekten anında gelir).

---

## Gerçek tema serileri (anahtarsız kaynaklar) — 14.11.2026 (Backend · Msi-nb)

`build_series(region)` artık **50 bölgenin 33'ünde gerçek veri** döndürür. Dönüş yapısı **değişmedi**:
`DataFrame{"Tarih", <spec.variable>}`, aylık, 2000-01 – 2024-12 (300 ay). `analyze()` aynı şekilde çalışır.

| Seri türü | Bölge sayısı | Kaynak | Değişken (regions.py) |
|---|---|---|---|
| `t2m` | 5 | NASA POWER MERRA-2 T2M | Aylık ortalama sıcaklık (°C) |
| `t2m_anom` | 4 | NASA POWER T2M − aynı ayın 2000–2024 ortalaması | Sıcaklık anomalisi (°C) |
| `ts_anom` | 2 | NASA POWER TS (yer yüzeyi) anomalisi | Yüzey sıcaklığı anomalisi (°C) |
| `t2m_max` | 4 | NASA POWER T2M_MAX | Aylık en yüksek sıcaklık (°C) |
| `precip` | 7 | NASA POWER PRECTOTCORR_SUM | Aylık yağış (mm) |
| `spei3` | 2 | NASA POWER günlük; Hargreaves PET; 3 aylık z-skor | Kuraklık indeksi (SPEI-3) |
| `aod` | 3 | NASA POWER AOD_55 (2001'den; 2000 aylık ortalamayla dolduruldu) | Aerosol optik derinliği |
| `sst` | 4 | NOAA ERSST v5 (ERDDAP, 2° hücre) | Deniz yüzeyi sıcaklığı (°C) |
| `co2` | 1 | NOAA GML Mauna Loa | Atmosferik karbondioksit (CO₂) (ppm) |
| `seaice_s` | 1 | NSIDC Sea Ice Index v4, Güney Yarımküre | Deniz buzu yayılımı (Güney Yarımküre) (milyon km²) |

**Sentetik kalan 17 bölge:** Akdeniz ve Kaliforniya (FWI), Grönland, Nil, Gobi ve Kanada (NDVI), İran (yeraltı
suyu), Nijer, Yangtze, Chao Phraya, Cava, ABD Doğu Kıyısı ve Everglades (deniz seviyesi / zemin çökmesi),
Kuzey Çin ve Hint-Ganj (PM2.5; Open-Meteo hava kalitesi geçmişi bu bölgelerde boş), Kıyı Dağları (kar),
And buzulları. Bunlar için Earthdata/Copernicus hesabı gerekir.

### Nasıl çalışır

1. `data_pipelines/snapshots/real_series.json`: depoya işlenmiş anlık görüntü (≈70 KB). 2000–2024 dönemi
   değişmediği için açılışta ağ isteği yapılmaz; internet yokken de gerçek veri gösterilir.
2. Anlık görüntüde olmayan bölge için canlı istek (`@st.cache_data(ttl=1800)`).
3. İkisi de olmazsa sentetik seri. İstisna fırlatılmaz.

Anlık görüntüyü yenilemek için: `.venv\Scripts\python -m data_pipelines.refresh_series` (≈13 sn).

### Yeni dışa aktarılanlar

| Ad | Ne yapar |
|---|---|
| `series_meta(region)` | `{"real", "kind", "source", "description", "origin" ("snapshot"\|"live"\|"synthetic"), "filled_months", "note"}`. Arayüz "gerçek / sentetik" etiketini buna göre göstermeli. |
| `real_series(region)` | Gerçek seri kaydı ya da `None` |
| `synthetic_series(region)` | Eski sentetik seri (karşılaştırma ve yedek için) |
| `REAL_SOURCES`, `KINDS` | Bölge → seri türü eşlemesi ve tür açıklamaları |

### Değişen bölge meta verileri (regions.py)

33 bölgenin `source` alanı gerçek kaynağı gösterecek şekilde güncellendi. Değişken adı değişenler:

- Marmara ve Meksika: "Yüzey sıcaklığı" → "Aylık ortalama sıcaklık"
- Büyük Göller: "Kış sıcaklığı anomalisi" → "Sıcaklık anomalisi"
- Sahra: "Toz aerosol optik derinliği" → "Aerosol optik derinliği"
- Antarktika: "Deniz buzu örtüsü (Weddell Denizi)" / % → **"Deniz buzu yayılımı (Güney Yarımküre)" / milyon km²** (yeni ad)
- Mauna Loa: "Atmosferik karbondioksit (XCO₂)" → **"Atmosferik karbondioksit (CO₂)"** (yeni ad; Mauna Loa yerinde
  ölçümdür, uydu XCO₂ değildir)

---

## Belirli tarih (ay/gün) ve geçmiş veri güvenilirliği — 14.11.2026 (Backend · Msi-nb)

### Belirli tarih desteği (geriye uyumlu)

| Fonksiyon | Yeni imza |
|---|---|
| `_fetch_weather` | `(start_year=0, end_year=None, month=None, day=None)` |
| `_fetch_grid` | `(start_year=0, end_year=None, month=None, day=None)` |
| `_fetch_historical_weather` / `_fetch_historical_grid` | `(year, month=None, day=None)` |
| `hist_date` | `(year, month=None, day=None)` → 12:00 UTC `datetime` |

- Tek tarih: `_fetch_weather(2019, None, 7, 15)` → 15 Temmuz 2019, 12:00 UTC. Izgara için de aynı.
- Ay verilip gün verilmezse ayın 15'i kullanılır. Geçersiz gün ayın son gününe çekilir (31 Şubat → 28/29 Şubat).
  Gelecekteki tarih bugüne çekilir.
- Aralık: `_fetch_weather(2005, 2023, 8, 1)` → iki yılın 1 Ağustos'u.
- Dönüş sözlüklerine eklenenler: `"month"`, `"day"`, `"date"` (`"YYYY-MM-DD"`), `"anomaly_live"`.
- Ay/gün verilmezse davranış eskisiyle aynı (o yılda bugünün takvim günü).

### "Canlı dışındaki tarihlerde veri gelmiyor" hatasının nedeni ve çözümü

1. **Başarısız sonuç 30 dakika önbelleğe yazılıyordu.** Meteomatics arşivi yoğun anlarda 30–60 sn gecikiyor;
   zaman aşımına düşen tarih yarım saat boyunca simülasyon (termal sapma 0, boş katman) olarak kalıyordu.
   Artık başarısızlık önbelleğe yazılmaz; aynı istek 90 sn sonra yeniden denenir (`RETRY_AFTER`).
2. **Yedek kaynak eklendi:** Open-Meteo ERA5 arşivi (anahtarsız). Sıra:
   - Anlık değerler: Meteomatics (8 sn sınır) → Open-Meteo ERA5 → simülasyon.
   - Termal sapma: Open-Meteo ERA5 (~1 sn) → Meteomatics → yok (`anomaly_live=False`).
3. **Anlık değer ve sapma istekleri paralel** gider.
4. **Kota sigortası:** Open-Meteo 429 döndürünce (dakikalık / saatlik / günlük kota) 1 / 15 / 60 dk boyunca hiç
   denenmez. Meteomatics zaman aşımına düşerse 2 dk atlanır. Böylece kaynak kapalıyken istek beklemeden yedeğe
   geçer. `source_status()` atlanan kaynakları ve kalan süreyi verir.
5. **Diske kalıcı önbellek:** `data_pipelines/cache/` (depoya girmez). Bir kez çekilen geçmiş tarih yeniden
   başlatmadan sonra da kota harcamadan anında gelir. Son 7 gün diske yazılmaz.
6. **Daha az kota:** Izgaranın termal sapması 264 yerine 30° kaba ızgarada (72 nokta) hesaplanıp 15°'ye ara
   değerlenir; canlı ızgara da aynı yöntemi kullanır (eskiden tek başına kotanın büyük kısmını tüketiyordu).

### Bilinmesi gerekenler

- **Open-Meteo ücretsiz kotası** konum başına sayılır (dakikada 600, saatte 5.000, günde 10.000; 2 haftadan uzun
  seriler katlanır). Yeni bir geçmiş tarih yaklaşık 350–700 birim harcar; diskteki tarihler hiç harcamaz.
  Demo öncesi kullanılacak tarihleri bir kez açmak (önbelleği ısıtmak) önerilir.
- **Meteomatics hackathon hesabı** yoğun arşiv isteklerinde yavaşlıyor; canlı veride sorun görülmedi.

---

## Veri kaynakları ve atıflar (Credits) — 14.11.2026 (Backend · Msi-nb)

`data_credits()` arayüzün Credits paneli için hazır içerik döndürür (`data_pipelines/credits.py`). Metinler Backend'de
tutulur; yeni bir kaynak eklendiğinde atıf da burada güncellenir.

```python
from data_pipelines import data_credits
c = data_credits()
# c["categories"]   → [{"id", "title_tr", "title_en", "items": [kayıt, ...]}, ...]   (5 kategori, 12 kaynak)
# kayıt             → id, category, name, provider, used_for_tr, used_for_en, url, license, (attribution), (citation)
# c["disclaimer_tr"] / c["disclaimer_en"]  → gerçek / sentetik bölge açıklaması (33 / 17)
# c["real_regions"], c["synthetic_regions"], c["series_kinds"], c["snapshot_generated"]
```

Kategoriler: hava (Meteomatics, Open-Meteo, ERA5) · iklim (NASA POWER, MERRA-2) · okyanus/karbon/buz (NOAA ERSST,
NOAA GML Mauna Loa, NSIDC) · yapay zekâ (Groq) · yazılım ve harita altlığı (Natural Earth, açık kaynak kütüphaneler,
Google Fonts). `attribution` alanı olan kaynaklarda bu metnin görünür olması kullanım koşulu gereğidir.

---

## Veri doğruluğu denetimi ve gerçekçi yedekler — 14.11.2026 (Backend · Msi-nb)

Proje sahibinin "bazen inandırıcı olmayan değerler görünüyor" bildirimi üzerine tüm kaynaklar denetlendi.

**Doğru çıkanlar:** Canlı Meteomatics verisi (50 bölgede fiziksel aralıkta ve iklim normaliyle uyumlu, ortalama
fark 3,3 °C), 33 gerçek tema serisi ve 17 sentetik seri (aralık dışı değer yok), NASA POWER trendleri.

**Sorun 1: yedek simülasyon gerçekçi değildi.** Kaynaklar düşünce gösterilen enlem formülü ay normalinden ortalama
5,9 °C, en fazla 26,6 °C sapıyordu (Grönland'da Kasım'da −7,7 °C; normal −34 °C). Rüzgâr her yerde sabit 15 km/sa,
nem boştu. **Düzeltme:** `climatology.py` + `snapshots/climatology.json`. 50 bölge ve 264 ızgara noktası için NASA
POWER aylık iklim normalleri (T2M, ortalama günlük fark, rüzgâr, nem, deniz seviyesine indirgenmiş basınç) kayıtlı.
Yedek değerler artık bu normallerden, gün içi saat dikkate alınarak üretilir. `source` alanında
"NASA POWER iklim normali (tahmini)" yazar ve `live` False kalır. Yenilemek için:
`.venv\Scripts\python -m data_pipelines.refresh_climatology`.

**Sorun 2: Open-Meteo kotası dolunca canlı termal sapma tamamen boşalıyordu** (50 bölgede 0, ızgara 0).
**Düzeltme:** Sapma alınamazsa iklim normaline göre sapma kullanılır (ölçülen sıcaklık − o saat ve ay için beklenen
sıcaklık).

**Yeni dönüş anahtarı: `anomaly_kind`** (`_fetch_weather`, `_fetch_grid`; canlı, geçmiş ve aralık):

| Değer | Anlamı | Arayüzde önerilen etiket |
|---|---|---|
| `"30d"` | Günün ortalaması − önceki 30 günün ortalaması | "Önceki 30 güne göre sapma" |
| `"climatology"` | Ölçülen sıcaklık − bu saat/ay için iklim normali (NASA POWER) | "İklim normaline göre sapma" |
| `None` | Sapma yok (`anomaly_live=False`) | Uyarı göster |

Yeni dışa aktarılanlar: `region_normals`, `normal_values`, `expected_temp`, `grid_normals`, `climatology_anomaly`.

**Not:** NASA POWER da yoğun isteklerde geçici 429 döndürüyor. Uygulama çalışırken yalnızca bölge kartının trend
isteği canlı gider (bölge başına 1 istek, 30 dk önbellek); normaller ve tema serileri diskten okunur.

---

## Sene ortalaması — 14.11.2026 (Backend · Msi-nb)

Frontend'in "Sene Ortalaması" seçeneği için (`data_pipelines/annual.py`):

| Fonksiyon | Dönüş |
|---|---|
| `_fetch_weather_annual(year)` | `_fetch_weather(year)` ile aynı şema. `data[bölge]`: `temp` (°C), `pressure` (hPa, deniz seviyesine indirgenmiş), `wind` (km/sa), `wind_dir` (°, aylık vektörlerin ortalaması), `humidity` (%), `anomaly` (yıllık ortalama − 1991–2020 ortalaması, °C), `label` "Sene ortalaması", `icon` "📅" |
| `_fetch_grid_annual(year)` | `_fetch_grid(year)` ile aynı şema (numpy 11 × 24): `temp`, `pressure`, `wind`, `wind_dir`, `anomaly` |

Ortak ek alanlar: `"annual": True`, `"date": "YYYY"`, `"time": "YYYY"`, `"month": None`, `"day": None`,
`"anomaly_live"`, `"anomaly_kind": "annual"`, `"source"` (ör. "NASA POWER (MERRA-2) · 2015 sene ortalaması · sapma:
1991–2020 normaline göre").

- **Kaynak:** NASA POWER aylık uç noktası (MERRA-2) yıllık ortalamaları. 1991–2025 için 50 bölge ve 264 ızgara noktası
  `snapshots/annual.json` dosyasında (≈390 KB). Okuma 0,1 sn sürer; ağ isteği ve kota yoktur.
- **Sapma tanımı:** Dünya Meteoroloji Örgütü standart normal dönemi 1991–2020. Doğrulama: ızgaranın alan ağırlıklı
  küresel sapması 2023 için +0,58 °C, 2024 için +0,64 °C. Copernicus'un aynı döneme göre resmî değerleri +0,60 ve
  +0,72 °C.
- **Kayıtta olmayan yıl** (ör. içinde bulunulan 2026): aylık iklim normallerinin yıllık ortalaması `live=False`,
  `anomaly_kind=None` ile döner. İstisna fırlatılmaz.
- **`anomaly_kind` yeni değeri:** `"annual"` → arayüz etiketi "1991–2020 ortalamasına göre yıllık sapma"
  (EN: "Annual deviation from 1991–2020 mean").
- **Yenilemek için** (yeni bir yıl tamamlandığında): `.venv\Scripts\python -m data_pipelines.refresh_annual` (~3 dk).
