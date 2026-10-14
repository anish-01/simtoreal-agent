"""D3.1: time 8 simulations one by one vs in parallel and record it in docs/benchmarks.md."""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import runlog
from pipeline import run_all, workers
from bench_models import write_section


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, default=ROOT / 'examples' / 'red_to_bin_a.json')
    parser.add_argument('--goals', default='{"red_part": "bin_a"}')
    parser.add_argument('-n', type=int, default=8)
    args = parser.parse_args()
    plan, goals = json.loads(args.plan.read_text()), json.loads(args.goals)
    plans = [dict(plan, plan_id=i) for i in range(1, args.n + 1)]

    times = {}
    for parallel in (False, True):
        run_dir = runlog.new_run(f'bench_sims parallel={parallel}')
        start = time.perf_counter()
        results = run_all(plans, goals, run_dir, parallel=parallel)
        times[parallel] = time.perf_counter() - start
        ok = sum(r['success'] for r in results)
        print(f"{'parallel' if parallel else 'one by one'}: {times[parallel]:.1f} s, {ok}/{len(plans)} succeeded")
    speedup = times[False] / times[True]
    lines = [f'Measured {datetime.now():%Y-%m-%d %H:%M} with `scripts/bench_sims.py` on {os.cpu_count()} CPU cores '
             f'({sys.platform}), {workers(args.n)} worker processes. {args.n} copies of `{args.plan.name}`, each with video and final image.\n',
             '| Measurement | Value |', '| --- | --- |',
             f'| {args.n} sims one by one | {times[False]:.1f} s |', f'| {args.n} sims in parallel | {times[True]:.1f} s |',
             f'| Speedup | {speedup:.1f}× |']
    print('Written to', write_section(f'Parallel simulation ({sys.platform})', lines))


if __name__ == '__main__':
    raise SystemExit(main())
