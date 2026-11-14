"""Seiron arayüz komutları (zaman, dil, paneller, grafik) — Frontend'in sohbetten siteyi yönetmesi için.

Bölge, yakınlaştırma ve katman komutlarını app.py zaten algılıyor (detect_navigation / detect_zoom / detect_layer).
Bu modül eksik kalanları ekler: zamanda yolculuk, sene ortalaması, dil, Credits paneli, görünümü sıfırlama ve sağ
paneldeki değerlerin grafiğini açma. Ağ isteği yapmaz, istisna fırlatmaz, saf fonksiyonlardır.

Güvenlik: yalnızca ALLOWED_ACTIONS içindeki arayüz eylemleri üretilir. Anahtar, şifre, önbellek, dosya, ayar ya da
kod çalıştırma gibi yönetici istekleri hiçbir eyleme dönüşmez; `denied=True` ve bir ret notu döner.
"""

from __future__ import annotations

import re

from .config import LAST_FULL_YEAR, NOW
from .regions import REGIONS

# Seiron'un dokunabileceği arayüz durumları (başka hiçbir şey).
ALLOWED_ACTIONS = ("year", "month", "lang", "panel", "chart", "reset_view")
DEFAULT_YEARS = tuple(range(LAST_FULL_YEAR, LAST_FULL_YEAR - 20, -1))   # app.py YEAR_OPTIONS ile aynı (0 hariç)

MONTHS_TR = ("ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül", "ekim", "kasım",
             "aralık")
MONTHS_EN = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
             "november", "december")
MONTHS_EN_SHORT = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")

_B = r"(?<![\wçğıöşü])"          # kelime başı (Türkçe ekler serbest)
_E = r"(?![\wçğıöşü])"           # kelime sonu

TIME_VERBS = ("git", "gidelim", "götür", "geç", "dön", "göster", "getir", "aç", "bak", "yolculuk", "seç", "ayarla",
              "ışınla", "zıpla", "atla", "ilerle", "ileri", "geri", "go to", "go back", "take me", "jump", "travel", "switch", "show",
              "back to", "set", "open", "move")
LIVE_WORDS = ("canlı", "canlıya", "günümüz", "şimdiki zaman", "gerçek zaman", "live", "real time", "real-time",
              "present day", "the present")
LIVE_SOFT = ("şimdi", "bugün", "şu an", "now", "today")            # yalnızca bir zaman fiiliyle birlikte
ANNUAL_WORDS = ("sene ortalama", "yıllık ortalama", "yıl ortalama", "yılın ortalama", "senenin ortalama",
                "tüm yıl", "bütün yıl", "year average", "annual average", "annual mean", "yearly average",
                "whole year")
PREV_YEAR = ("önceki yıl", "önceki sene", "bir yıl geri", "bir sene geri", "1 yıl geri", "1 sene geri",
             "previous year", "one year back", "a year back", "year earlier")
NEXT_YEAR = ("sonraki yıl", "sonraki sene", "bir yıl ileri", "bir sene ileri", "1 yıl ileri", "1 sene ileri",
             "next year", "one year forward", "a year forward", "year later")
PREV_MONTH = ("önceki ay", "bir ay geri", "1 ay geri", "previous month", "one month back", "a month back")
NEXT_MONTH = ("sonraki ay", "bir ay ileri", "1 ay ileri", "next month", "one month forward", "a month forward")
LAST_YEAR = ("geçen yıl", "geçen sene", "last year")

LANG_EN = ("ingilizce", "english", "ingilizceye")
LANG_TR = ("türkçe", "turkish", "türkçeye")
LANG_VERBS = ("geç", "değiştir", "konuş", "çevir", "dil", "switch", "change", "speak", "use", "language", "set")

CREDITS_WORDS = ("credits", "kredi", "atıf", "kaynakça", "veri kaynakları", "kaynakları göster", "lisans",
                 "data sources", "attribution")
CLOSE_WORDS = ("kapat", "gizle", "close", "hide", "dismiss")
OPEN_WORDS = ("aç", "göster", "getir", "open", "show", "display")
RESET_WORDS = ("görünümü sıfırla", "kamerayı sıfırla", "haritayı sıfırla", "başa dön", "ilk görünüm",
               "reset view", "reset camera", "reset the view", "reset map")

# Sağ paneldeki değerler → metric_chart() anahtarı
CHART_WORDS = {
    "tau": ("kendall", "tau", "τ"),
    "p": ("p-değer", "p değer", "p value", "p-value", "anlamlılık", "significance", "z skor", "z-skor", "z score"),
    "slope": ("sen eğilim", "sen slope", "eğim", "on yıllık", "per decade", "eğilim yön", "trend direction",
              "projeksiyon", "projection"),
    "power_t": ("sıcaklık eğilim", "temperature trend", "uzun vadeli", "long-term", "nasa power"),
}
CHART_NOUNS = ("grafi", "grafik", "chart", "graph", "plot", "eğri", "dağılım", "curve")

ADMIN_WORDS = ("api anahtar", "api key", "şifre", "parola", "password", "secret", "token", "önbelleği temizle",
               "cache temizle", "clear cache", "admin", "yönetici", "sudo", "root yetki", "dosyayı sil", "delete file",
               "kodu çalıştır", "run code", "execute", "terminal", "sunucuyu kapat", "shutdown", "restart server",
               "ayarları değiştir", "secrets.toml")


def _lower(text: str) -> str:
    return (text or "").replace("I", "ı").replace("İ", "i").lower()


# Kelime başı eşleşmesinde yanlış pozitif veren uzun sözcükler ("açıkla" ≠ "aç", "geçmiş" ≠ "geç")
_FALSE_STARTS = ("açıkla", "açık", "geçmiş", "gerek", "gerç", "setting", "showcase")


def _has(q: str, words) -> bool:
    for w in words:
        for m in re.finditer(_B + re.escape(w), q):
            tail = q[m.start():m.start() + 12]
            if not any(tail.startswith(f) and not w.startswith(f) for f in _FALSE_STARTS):
                return True
    return False


def _month_in(q: str) -> int | None:
    for i, (tr, en) in enumerate(zip(MONTHS_TR, MONTHS_EN)):
        if re.search(_B + tr, q):
            return i + 1
        if en == "may":   # İngilizcede "may" yardımcı fiil de olabilir: yalnızca sayıyla yan yana
            if re.search(_B + r"(?:\d{1,4}\s+may|may\s+\d{1,4})" + _E, q):
                return i + 1
        elif re.search(_B + en + _E, q):
            return i + 1
    for i, en in enumerate(MONTHS_EN_SHORT):   # "Mar 2019" — yalnızca yılla birlikte
        if re.search(_B + en + r"\.?\s+(19|20)\d{2}" + _E, q):
            return i + 1
    return None


def _note(tr: str, en: str, lang: str) -> str:
    return en if lang == "en" else tr


def parse_ui_command(text: str, year: int = 0, month: int = 0, lang: str = "tr",
                     years: tuple[int, ...] | list[int] | None = None) -> dict:
    """Sohbet metnindeki arayüz komutlarını çözer.

    Giriş: kullanıcı metni ve arayüzün o anki durumu (year: 0 = canlı, month: 0 = sene ortalaması, lang "tr"/"en").
    `years` seçilebilir yıllar (varsayılan: son 20 tam yıl, app.py YEAR_OPTIONS ile aynı).

    Dönüş (yalnızca değişecek alanlar dolu; None = dokunma):
      {"matched": bool, "denied": bool,
       "year": int|None (0 = canlı), "month": int|None (0 = sene ortalaması, 1–12),
       "day": int|None (bilgi: metinde gün geçtiyse; arayüz ayın 15'ini kullanır),
       "lang": "tr"|"en"|None, "panel": "credits_open"|"credits_close"|None,
       "chart": "tau"|"p"|"slope"|"power_t"|None, "reset_view": bool,
       "notes": [str] (seçili dilde kısa açıklamalar: ne yapıldı / neden yapılamadı)}
    İstisna fırlatmaz.
    """
    out = {"matched": False, "denied": False, "year": None, "month": None, "day": None, "lang": None,
           "panel": None, "chart": None, "reset_view": False, "notes": []}
    try:
        return _parse(text, int(year or 0), int(month or 0), "en" if lang == "en" else "tr",
                      tuple(years) if years else DEFAULT_YEARS, out)
    except Exception:
        return out


def _parse(text: str, year: int, month: int, lang: str, years: tuple[int, ...], out: dict) -> dict:
    q = _lower(text)
    if not q.strip():
        return out
    notes = out["notes"]
    lo, hi = min(years), max(years)

    if _has(q, ADMIN_WORDS):
        out["denied"] = True
        notes.append(_note("Bu bir yönetici işlemi; Seiron yalnızca harita, zaman, dil ve panelleri yönetebilir.",
                           "That is an administrative action; Seiron can only control the map, time, language and "
                           "panels.", lang))
        return _done(out)

    verb = _has(q, TIME_VERBS)
    short = len(q.split()) <= 5

    # ── Dil
    if _has(q, LANG_VERBS) or short:
        if _has(q, LANG_EN) and lang != "en":
            out["lang"] = "en"
        elif _has(q, LANG_TR) and lang != "tr":
            out["lang"] = "tr"

    # ── Credits paneli ve görünüm
    if _has(q, CREDITS_WORDS):
        if _has(q, CLOSE_WORDS):
            out["panel"] = "credits_close"
        elif _has(q, OPEN_WORDS) or short:
            out["panel"] = "credits_open"
    if any(w in q for w in RESET_WORDS):
        out["reset_view"] = True

    # ── Grafik penceresi (sağ paneldeki değerler)
    noun, opener = _has(q, CHART_NOUNS), _has(q, OPEN_WORDS)
    if (noun and (opener or "?" not in q)) or opener:
        for key, words in CHART_WORDS.items():
            if any(w in q for w in words) and (noun or key != "power_t"):
                out["chart"] = key
                break

    # ── Zaman
    new_year, new_month = None, None
    yrs = [int(m) for m in re.findall(_B + r"((?:19|20)\d{2})" + _E, q)]
    mon = _month_in(q)
    if any(re.search(_B + re.escape(w), q) for w in LIVE_WORDS) or (verb and _has(q, LIVE_SOFT) and not yrs):
        new_year, new_month = 0, 0
    elif yrs and (verb or mon or (short and "?" not in q)):
        y = yrs[0]
        if lo <= y <= hi:
            new_year = y
        elif y > hi:
            notes.append(_note(f"{y} için arşiv verisi yok; seçilebilir yıllar {lo}–{hi}. Geleceğe dair bir fikir için "
                               "zaman serisi grafiğindeki 2034 uzatımına bakabilirsin (öngörü değil, eğilimin doğrusal "
                               "devamı). Canlı veriye geçmek için \"canlıya dön\" de.",
                               f"There is no archive data for {y}; available years are {lo}–{hi}. For a look ahead, see "
                               "the 2034 extension on the time-series chart (a linear continuation of the trend, not a "
                               "forecast). Say \"back to live\" for current data.", lang))
        else:
            new_year = lo
            notes.append(_note(f"{y} arşiv aralığının dışında; en eski yıl {lo} seçildi.",
                               f"{y} is outside the archive range; the earliest year, {lo}, was selected.", lang))
    else:
        m_ago = re.search(_B + r"(\d{1,2}|bir|iki|üç|beş|on)\s*(?:yıl|sene)\s*(?:önce|evvel)|(\d{1,2})\s*years?\s+ago", q)
        words = {"bir": 1, "iki": 2, "üç": 3, "beş": 5, "on": 10}
        if m_ago:
            raw = m_ago.group(1) or m_ago.group(2)
            n = words.get(raw) or int(raw)
            new_year = min(max(NOW.year - n, lo), hi)
        elif _has(q, LAST_YEAR):
            new_year = min(max(NOW.year - 1, lo), hi)
        elif _has(q, PREV_YEAR):
            new_year = max((year or hi + 1) - 1, lo)
        elif _has(q, NEXT_YEAR):
            if not year:
                notes.append(_note("Zaten canlı verideyiz; ileri bir yıl yok.", "Already on live data; there is no "
                                   "later year.", lang))
            else:
                new_year = year + 1 if year + 1 <= hi else 0
        elif _has(q, PREV_MONTH) or _has(q, NEXT_MONTH):
            step = -1 if _has(q, PREV_MONTH) else 1
            if not year:   # canlıdan: arşivin son ayı (içinde bulunulan yıl arşivde yok)
                y, m = hi, 12 + (1 if step < 0 else 0)
                if step < 0:
                    notes.append(_note(f"Arşiv {hi} Aralık ile bitiyor; o ay seçildi.",
                                       f"The archive ends in December {hi}; that month was selected.", lang))
            else:
                y, m = year, (month or NOW.month)
            m += step
            if m < 1:
                y, m = y - 1, 12
            elif m > 12:
                y, m = y + 1, 1
            if y < lo:
                notes.append(_note(f"Arşiv {lo} Ocak ile başlıyor.", f"The archive starts in January {lo}.", lang))
            elif y > hi:
                new_year, new_month = 0, 0
            else:
                new_year, new_month = y, m

    if mon and new_month is None and (new_year not in (None, 0) or yrs or verb or year):
        new_month = mon
        if new_year is None and not year:
            new_year = hi
            notes.append(_note(f"Yıl belirtilmedi; en son tam yıl ({hi}) kullanıldı.",
                               f"No year given; the latest full year ({hi}) was used.", lang))
        dm = re.search(_B + r"([1-9]|[12]\d|3[01])\s+" + (MONTHS_TR[mon - 1] if re.search(_B + MONTHS_TR[mon - 1], q)
                                                           else MONTHS_EN[mon - 1]), q)
        if dm:
            out["day"] = int(dm.group(1))
            notes.append(_note("Arayüz gün seçimi sunmuyor; ayın 15'i (12:00 UTC) gösteriliyor.",
                               "The interface has no day picker; the 15th of the month (12:00 UTC) is shown.", lang))
    if _has(q, ANNUAL_WORDS) and new_month is None:
        new_month = 0
        if new_year is None and not year:
            new_year = hi
    if new_year is not None and new_year != 0 and new_month is None and new_year != year:
        new_month = 0          # yeni yıla geçerken varsayılan: sene ortalaması (app.py ile aynı)

    if new_year is not None and new_year != year:
        out["year"] = new_year
    if new_month is not None and (new_month != month or out["year"] is not None):
        out["month"] = new_month if (out["year"] if out["year"] is not None else year) else None
    return _done(out)


def _done(out: dict) -> dict:
    # Not varsa da eşleşmiş say: ör. "2099'a git" hiçbir şeyi değiştirmez ama kullanıcıya nedenini söylemek gerekir.
    out["matched"] = bool(out["denied"] or out["reset_view"] or out["notes"]
                          or any(out[k] is not None for k in ALLOWED_ACTIONS if k != "reset_view"))
    return out


def time_text(year: int, month: int = 0, lang: str = "tr") -> str:
    """Seçili zamanın kısa adı: "canlı veri" / "2019 sene ortalaması" / "Mart 2019"."""
    if not year:
        return _note("canlı veri", "live data", lang)
    if not month:
        return _note(f"{year} sene ortalaması", f"{year} year average", lang)
    names = MONTHS_EN if lang == "en" else MONTHS_TR
    return f"{names[month - 1].capitalize()} {year}"


def switch_message(city: str, lang: str = "tr", year: int = 0, month: int = 0) -> str:
    """Karşılamadan sonraki bölge geçişlerinde Seiron'un kısa notu (yeniden "Merhaba" demeden).

    Ör. "🧭 Şu an İber Yarımadası bölgesine bakıyoruz · canlı veri."
    """
    spec = REGIONS.get(city)
    if spec is None:
        return ""
    when = time_text(year, month, lang)
    if lang == "en":
        name = spec.en[0] or city
        theme = spec.en[2] or spec.theme
        return f"🧭 We are now looking at **{name}** · {theme} · {when}."
    return f"🧭 Şu an **{city}** bölgesine bakıyoruz · {spec.theme} · {when}."
