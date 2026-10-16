"""Explicit operator approval produces files, never real-robot commands."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import planner
import scorer

EXPORTS = Path(__file__).resolve().parent / 'exports'
NAMES = {'red_part': 'red part', 'blue_part': 'blue part', 'bin_a': 'bin A', 'bin_b': 'bin B'}


def readable_step(step):
    action = step['action']
    if action == 'move_to':
        return f"Move above {NAMES[step['target']]}"
    if action == 'lift':
        return f"Lift {step.get('height', .15):g} meters"
    return {'grasp': 'Grasp the part', 'release': 'Release the part', 'home': 'Return to the starting pose'}[action]


def export_approved(result, reviewed=False, root=EXPORTS):
    if not result or result.get('error') or not result.get('best'):
        raise ValueError('No safe plan is available. Test a task before approving.')
    best = result['best']
    if best.get('status') != 'OK' or scorer.score([best.get('result', {})])[0]['status'] != 'OK':
        raise ValueError('This plan failed a simulation safety check and cannot be exported.')
    plan = next((p for p in result.get('plans', []) if p.get('plan_id') == best['plan_id']), None)
    if plan is None:
        raise ValueError('The selected plan is missing. Test the task again.')
    valid, reason = planner.validate(plan)
    if not valid:
        raise ValueError(f'The selected plan is invalid: {reason}')
    vision = best.get('vision') or {}
    if vision.get('needs_review', True) and not reviewed:
        raise ValueError('Review the video and final image, then tick the human-review acknowledgement before approving.')
    approved_at = datetime.now(timezone.utc).isoformat()
    payload = dict(task=result['task'], run_id=result['run_id'], goals=result.get('goals'),
                   score=best['score'], approved_at=approved_at, vision=vision,
                   human_reviewed=bool(reviewed), plan=plan, simulation=best['result'],
                   execution='Export only; no real robot commanded')
    steps = '\n'.join(f'{i}. {readable_step(step)}' for i, step in enumerate(plan['steps'], 1))
    text = f"Task: {result['task']}\nRun: {result['run_id']}\nScore: {best['score']}/100\nApproved (UTC): {approved_at}\n\n{steps}\n\nExport only; no real robot commanded.\n"
    folder = Path(root) / uuid4().hex
    folder.mkdir(parents=True)
    program, readable = folder / 'program.json', folder / 'steps.txt'
    program.write_text(json.dumps(payload, indent=2) + '\n')
    readable.write_text(text)
    return program, readable
