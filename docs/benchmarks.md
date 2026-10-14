# Benchmarks

## Parallel simulation (darwin)

Measured 2026-10-14 01:29 with `scripts/bench_sims.py` on 8 CPU cores (darwin), 4 worker processes. 8 copies of `red_to_bin_a.json`, each with video and final image.

| Measurement | Value |
| --- | --- |
| 8 sims one by one | 16.0 s |
| 8 sims in parallel | 10.4 s |
| Speedup | 1.5× |
