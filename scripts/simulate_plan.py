"""Day 2: saved JSON or typed task -> measured simulation and MP4."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulator import run_plan
from runlog import new_run, save_json


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--task', help='Send a typed task to the configured AMD planner')
    source.add_argument('--plan', type=Path, help='Read a saved single plan JSON')
    parser.add_argument('--goals', required=True, help='JSON mapping, e.g. {"red_part":"bin_a"}')
    args = parser.parse_args()
    goals = json.loads(args.goals)
    folder = new_run(args.task or f'Saved plan: {args.plan}')
    if args.task:
        from planner import request_plan
        plan, reason, _ = request_plan(args.task)
        if plan is None:
            print(f'Planner failed: {reason}')
            return 1
    else:
        plan = json.loads(args.plan.read_text())
    save_json(folder, 'plans.json', [plan])
    save_json(folder, 'goals.json', goals)
    result = run_plan(plan, goals, folder)
    save_json(folder, 'results.json', [result])
    print(json.dumps(result, indent=2))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
