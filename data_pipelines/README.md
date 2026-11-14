# data_pipelines/ — VULPA veri katmanı

**Sahibi:** 2. yapay zekâ asistanı (Backend / veri çekme).
**Frontend asistanı bu klasöre yazmaz.** Frontend `app.py` ve `components/` dosyalarından sorumludur.

## Görev sınırı

| Alan | Sorumlu | Klasör / dosya |
|---|---|---|
| Veri çekme, API'ler, önbellek, istatistik | 2. asistan | `data_pipelines/` |
| Arayüz, düzen, küre, Seiron paneli | Frontend asistanı | `app.py`, `components/` |

## Şu an app.py içinde duran veri kodu

Bu fonksiyonlar henüz `app.py` içinde ve çalışıyor. Buraya taşınacaklarsa, Frontend'in arayüzü bozulmasın
diye **ad, parametre ve dönüş yapıları aynı kalmalı**. Taşındıktan sonra Frontend, `app.py` içindeki
`import` satırlarını günceller.

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
