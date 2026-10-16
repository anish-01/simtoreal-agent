# Benchmarks

## Parallel simulation (darwin)

Measured 2026-10-14 01:29 with `scripts/bench_sims.py` on 8 CPU cores (darwin), 4 worker processes. 8 copies of `red_to_bin_a.json`, each with video and final image.

| Measurement | Value |
| --- | --- |
| 8 sims one by one | 16.0 s |
| 8 sims in parallel | 10.4 s |
| Speedup | 1.5× |

## Live AMD Token Factory validation — October 16, 2026

Authenticated `/models` returned 16 models. The shared API at
`https://developer.amd.com.cn/radeon/api/v1` accepted the team key.
`DeepSeek-V4-Flash` generated goals and eight candidate plans per task;
`DeepSeek-V4.1-Flash` checked the best final image when a safe candidate existed.
MuJoCo simulation ran **locally on macOS, with four worker processes**. Model
inference was hosted by AMD Token Factory. The gateway did not report a GPU SKU,
ROCm version, vLLM version, token throughput, or server-side GPU timing. These
results must not be described as measured MI300X performance or AMD simulation
speedup.

| Live task | Valid plans | Accepted by simulation | Rejected | Planning wall time | Vision wall time | Total wall time |
| --- | --- | --- | --- | --- | --- | --- |
| Red to bin A | 8 | 6 | 2 dropped parts | 5.715 s | 7.960 s | 20.570 s |
| Sort both parts | 8 | 6 | 2 dropped parts | 8.111 s | 97.555 s | 115.485 s |
| Blue part out of reach | 8 | 0 | 8 unreachable target | 6.247 s | Not invoked | 9.786 s |

Source: pipeline `results.json` from local runs `20261016-133954` and
`20261016-134119`, plus `20261016-134420` for the unreachable task. All three
tasks met their expected simulation outcomes: 24 plans, 12 accepted and 12
rejected, with no best plan selected for the impossible task. The pipeline
measures planning, simulation and vision with
`time.perf_counter()` around each stage; total includes goal extraction. The
planning rates were 1.40 and 0.99 valid plans per second respectively. These are
client-observed wall times including network/service delays, not token/sec or
pure GPU execution time. Each measurement is a single run, not an average or SLA.

Both image checks returned `answer=no`, `confidence=1`, while geometry checks
passed. Both responses correctly produced `needs_review=true`. In the red-only
best-plan image, the arm obscures the bottom bin and red part; in the sorting
image, the arm obscures the top bin and blue part. Vision confidence
does not establish correctness; these exports require explicit human inspection
and acknowledgement. This validates the disagreement handling, not automatic
visual confirmation of task success.

The account reported a shared limit of 20 requests per minute. Runs were spaced
by 65 seconds to leave room for other team usage. Keys, account identifiers and
raw authorization headers are excluded from this record.
