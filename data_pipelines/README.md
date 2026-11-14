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
