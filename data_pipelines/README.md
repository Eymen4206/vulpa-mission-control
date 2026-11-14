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
