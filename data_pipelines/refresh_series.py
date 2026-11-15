"""Gerçek tema serilerinin anlık görüntüsünü (snapshots/real_series.json) yeniden üretir.

Kullanım (proje kökünden):
    .venv\\Scripts\\python -m data_pipelines.refresh_series          (yalnızca yeni bölgeler: --new)

REAL_SOURCES içindeki tüm bölgelerin verisini anahtarsız kaynaklardan paralel olarak çeker. Başarısız olan bölgelerin eski kaydı
korunur; hiçbir bölge silinmez.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor

try:  # Antivirüs / kurumsal proxy sertifikaları için
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

from .real_series import REAL_SOURCES, SNAPSHOT_PATH, fetch_real_series, load_snapshot, write_snapshot


def main() -> int:
    old = load_snapshot().get("regions", {}) if SNAPSHOT_PATH.exists() else {}
    records, failed = dict(old), []
    t0 = time.time()
    # --new: yalnızca anlık görüntüde olmayan bölgeler çekilir (mevcut kayıtlar aynen kalır)
    names = [n for n in REAL_SOURCES if not ("--new" in sys.argv and n in old)]

    def work(name: str):
        try:
            return name, fetch_real_series(name), None
        except Exception as exc:  # noqa: BLE001 — betik: hatayı raporla, devam et
            return name, None, f"{exc.__class__.__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=6) as pool:
        for name, rec, err in pool.map(work, names):
            if rec:
                records[name] = rec
                print(f"  ✓ {name:28} {rec['kind']:9} doldurulan ay: {rec['filled']}")
            else:
                failed.append(name)
                print(f"  ✗ {name:28} {err}")
    path = write_snapshot(records)
    print(f"\n{len(records)}/{len(REAL_SOURCES)} bölge yazıldı → {path}  ({time.time() - t0:.1f} sn)")
    if failed:
        print("Başarısız (eski kayıt korundu):", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
