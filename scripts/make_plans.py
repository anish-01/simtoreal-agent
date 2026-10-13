"""D2.1/D2.2: typed task -> 8 plans from the LLM -> runs/<run_id>/plans.json."""
import argparse
import json
import logging
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planner
import runlog


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('task')
    parser.add_argument('-n', type=int, default=8)
    args = parser.parse_args()
    logging.basicConfig(format='%(message)s')

    run_dir = runlog.new_run(args.task)
    start = time.perf_counter()
    plans = planner.generate_plans(args.task, n=args.n)
    seconds = time.perf_counter() - start
    runlog.save_json(run_dir, 'plans.json', plans)

    distinct = {json.dumps(p['steps'], sort_keys=True) for p in plans}
    for p in plans:
        print(p['plan_id'], ' -> '.join(s['action'] + (f" {s['target']}" if 'target' in s else '') for s in p['steps']))
    print(f'{len(plans)}/{args.n} valid, {len(distinct)} different, {seconds:.2f} s. Saved {run_dir}/plans.json')
    return 0 if plans else 1


if __name__ == '__main__':
    raise SystemExit(main())
