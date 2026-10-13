"""P7: send the five test tasks to the planner LLM and record the replies in docs/prompt_tests.md."""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planner

TASKS = [
    'Put the red part in bin A',
    'Put the blue part in bin B',
    'Sort both parts by color: red part to bin A, blue part to bin B',
    'Put both parts in bin B',
    'Move the blue part to bin A, then go home',
]
OUT = Path(__file__).resolve().parents[1] / 'docs' / 'prompt_tests.md'


def main():
    llm = planner.client()
    rows, details, passed = [], [], 0
    for n, task in enumerate(TASKS, 1):
        start = time.perf_counter()
        plan, reason, raw = planner.request_plan(task, temperature=.2, plan_id=n, llm=llm)
        seconds = time.perf_counter() - start
        passed += plan is not None
        status = 'valid' if plan else f'invalid: {reason}'
        print(f'{n}. {task}: {status} ({seconds:.2f} s)')
        rows.append(f'| {n} | {task} | {status} | {seconds:.2f} |')
        body = json.dumps(plan, indent=2) if plan else raw
        details.append(f'### {n}. {task}\n\n```json\n{body}\n```\n')
    model = os.getenv('LLM_MODEL') or 'Qwen/Qwen3-8B'
    OUT.write_text(
        f'# Planner prompt tests\n\n'
        f'Run {datetime.now():%Y-%m-%d %H:%M} with `{model}`, temperature 0.2, thinking off, JSON mode. '
        f'Prompt: `planner.SYSTEM_PROMPT`. Times include network latency.\n\n'
        f'**Result: {passed}/{len(TASKS)} valid.**\n\n'
        f'| # | Task | Result | Seconds |\n| --- | --- | --- | --- |\n' + '\n'.join(rows) +
        '\n\n## Replies\n\n' + '\n'.join(details))
    print(f'{passed}/{len(TASKS)} valid; written to {OUT.relative_to(Path.cwd()) if OUT.is_relative_to(Path.cwd()) else OUT}')
    return 0 if passed == len(TASKS) else 1


if __name__ == '__main__':
    raise SystemExit(main())
