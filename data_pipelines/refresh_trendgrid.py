# SI disclosure (NASA Space Apps Challenge 2026): this file was written with Super Intelligence (SI) assistance,
# Claude / Claude Code (Anthropic), and reviewed by the VULPA team (Mete, Yahya, Eymen). Details: README.md.
"""Trend haritası anlık görüntüsünü (snapshots/trendgrid.json) üretir: 264 ızgara noktası × 15 değişken, yıllık değerler.

Kullanım (proje kökünden):  .venv\\Scripts\\python -m data_pipelines.refresh_trendgrid
NASA POWER yoğun isteklerde 429 döndürdüğü için 3 paralel işçi ve artan bekleme kullanılır (~5–10 dk).
Her nokta aynı zamanda variables.py disk önbelleğine yazılır (nokta analizi de hızlanır).
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor

try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

import numpy as np

from .config import GRID_LATS, GRID_LONS
from .trendgrid import annual_from_raw, load_trendgrid, write_trendgrid
from .variables import _point_raw, _window


def main() -> int:
    t0 = time.time()
    y0, y1 = _window(None)
    la, lo = np.meshgrid(GRID_LATS, GRID_LONS, indexing="ij")
    jobs = list(zip(la.ravel().tolist(), lo.ravel().tolist()))
    old = load_trendgrid()
    old_pts = old.get("points") if old.get("years") == [y0, y1] else None
    done = [0]

    def work(args):
        lat, lon = args
        for attempt in range(6):
            try:
                raw = _point_raw(float(lat), float(lon), y0, y1)
                res = annual_from_raw(raw["params"], y0, y1)
                break
            except Exception:
                time.sleep(15 * (attempt + 1))
        else:
            res = None
        done[0] += 1
        if done[0] % 24 == 0:
            print(f"  {done[0]}/{len(jobs)} ({time.time() - t0:.0f} sn)", flush=True)
        return res

    with ThreadPoolExecutor(max_workers=3) as pool:
        points = list(pool.map(work, jobs))
    points = [p if p else (old_pts[i] if old_pts and i < len(old_pts) else None) for i, p in enumerate(points)]
    missing = sum(p is None for p in points)
    if missing:
        print(f"{missing} nokta alınamadı; dosya yazılmadı. Biraz sonra tekrar çalıştırın (alınanlar disk önbelleğinde).")
        return 1
    path = write_trendgrid(points, y0, y1)
    print(f"{len(points)} nokta → {path} ({time.time() - t0:.0f} sn)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
