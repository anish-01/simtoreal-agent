"""Verify three demos through the backend, with saved plans or the live AMD planner."""
import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planner
from demo_tasks import DEMO_TASKS, expected_outcome
from pipeline import run_task


class SavedPlanClient:
    """Explicit offline fixture; no model inference or AMD performance measurement."""
    def __init__(self, demo):
        self.demo = demo
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        if kwargs['messages'][0]['content'] == planner.GOALS_PROMPT:
            reply = {'goals': self.demo['goals']}
        else:
            reply = json.loads(self.demo['plan'].read_text())
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reply)))])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Use the configured AMD endpoint instead of saved plans')
    parser.add_argument('--demo', choices=['all', *DEMO_TASKS], default='all')
    parser.add_argument('-n', type=int, choices=range(1, 9), default=8)
    parser.add_argument('--sequential', action='store_true')
    args = parser.parse_args()
    print('Live AMD planner' if args.live else 'Offline saved plans: no AMD inference')
    passed = True
    for name in DEMO_TASKS if args.demo == 'all' else [args.demo]:
        demo = DEMO_TASKS[name]
        result = run_task(demo['task'], n=args.n, scene=demo['scene'],
                          llm=None if args.live else SavedPlanClient(demo), parallel=not args.sequential)
        ok = expected_outcome(name, result)
        passed = passed and ok
        print(json.dumps(dict(demo=name, passed=ok, run_dir=result['run_dir'],
                              accepted=sum(row['status'] == 'OK' for row in result['table']),
                              error=result['error'], table=[{k: row[k] for k in ('plan_id', 'score', 'status', 'reason')}
                                                            for row in result['table']]), indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
