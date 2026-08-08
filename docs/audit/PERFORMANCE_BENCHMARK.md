# Master Audit Offline Performance Benchmark

Command:

```powershell
python scripts/benchmark_master_audit.py
```

Environment: Python 3.14.5, Windows, 2026-08-09. The benchmark uses all 80
registry rows and 72 adapters against deterministic synthetic pages, excludes
external network latency, and measures Python allocations with `tracemalloc`.

| Pages | Time | Peak traced memory | Findings | Coverage rows |
|---:|---:|---:|---:|---:|
| 100 | 0.083 s | 0.44 MiB | 407 | 80 |
| 1,000 | 0.759 s | 3.80 MiB | 4,007 | 80 |
| 5,000 | 3.900 s | 18.67 MiB | 20,007 | 80 |

The 500-page DoD thresholds (<5 minutes and <512 MiB, excluding external APIs)
are comfortably inside these measured 5,000-page results. Values are
environment-specific; rerun the committed script after material algorithm or
runtime changes.
