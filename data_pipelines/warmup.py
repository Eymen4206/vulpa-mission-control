"""Açılış ısınması: sayfa çizilmeden önce gereken tüm veriyi paralel olarak önbelleğe alır.

Proje sahibi: "site yüklenene kadar açılmasın, buglu gibi duruyor". Frontend tam ekran yükleme kartının arkasında
`warm_up(...)` çağırır, ardından sayfayı çizer. Çizim sırasında tüm çağrılar önbellekten gelir; sayfa parça parça
belirmez. Çağrılar app.py'deki fetch_weather / fetch_grid / fetch_power ile birebir aynı argümanlarla yapılır (önbellek
anahtarı aynı olsun diye). Bekleme süresi toplam değil, en yavaş kaynak kadardır.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .annual import _fetch_grid_annual, _fetch_weather_annual
from .config import LAST_FULL_YEAR, POWER_SPAN
from .grid import _fetch_grid
from .power import _fetch_power
from .regions import REGIONS
from .series import analyze, build_series
from .weather import _fetch_weather


def _jobs(region: str | None, year: int, month: int | None, day: int | None) -> list[tuple[str, callable, tuple]]:
    year = int(year or 0)
    if year and not month:
        weather = ("weather", _fetch_weather_annual, (year,))
        grid = ("grid", _fetch_grid_annual, (year,))
    elif year:
        weather = ("weather", _fetch_weather, (year, None, month, day))
        grid = ("grid", _fetch_grid, (year, None, month, day))
    else:
        weather = ("weather", _fetch_weather, (0,))
        grid = ("grid", _fetch_grid, (0,))
    jobs = [weather, grid]
    if region in REGIONS:
        end = year or LAST_FULL_YEAR
        jobs += [("power", _fetch_power, (region, end - POWER_SPAN + 1, end)),
                 ("series", build_series, (region,)), ("analysis", analyze, (region,))]
    return jobs


def warm_up(region: str | None = None, year: int = 0, month: int | None = None, day: int | None = None,
            on_step=None) -> dict:
    """Seçili bölge ve zaman için gereken veriyi paralel çeker (hava, ızgara, NASA POWER, tema serisi, analiz).

    Argümanlar app.py'deki `sel_date()` ile aynı: year 0 = canlı; month None/0 = sene ortalaması.
    `on_step(done, total, name)`: her iş bitince çağrılır (ilerleme çubuğu için; ana iş parçacığında çağrılır).
    Dönüş: {"ok": bool, "seconds": float, "steps": {ad: {"ok": bool, "seconds": float}}}.
    İstisna fırlatmaz. Bir kaynak düşerse ilgili fonksiyon zaten kendi yedeğini döndürür; ok=False yalnızca beklenmedik
    hatadır.
    """
    month = month or None
    jobs = _jobs(region, year, month, day)
    t0 = time.time()
    steps: dict[str, dict] = {}
    try:
        from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
        ctx = get_script_run_ctx()
    except Exception:
        ctx, add_script_run_ctx = None, None

    def run(name, fn, args):
        if ctx is not None and add_script_run_ctx is not None:
            import threading
            add_script_run_ctx(threading.current_thread(), ctx)
        s = time.time()
        try:
            fn(*args)
            return name, True, time.time() - s
        except Exception:
            return name, False, time.time() - s

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(run, *j) for j in jobs]
        for f in as_completed(futures):
            name, ok, sec = f.result()
            steps[name] = {"ok": ok, "seconds": round(sec, 2)}
            if on_step is not None:
                try:
                    on_step(len(steps), len(jobs), name)
                except Exception:
                    pass
    return {"ok": all(s["ok"] for s in steps.values()), "seconds": round(time.time() - t0, 2), "steps": steps}
