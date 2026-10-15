"""Scorer: scores simulated plans and rejects unsafe ones."""
import math


def _positive_number(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value > 0)


def _rejection(result):
    if result.get('collisions', 0):
        return 'Rejected: arm hit the table'
    if result.get('dropped', False):
        return 'Rejected: dropped part'
    if result.get('failed_step') is not None:
        return f"Rejected: step {result['failed_step']} failed ({result.get('reason') or 'action failed'})"
    if result.get('success') is not True:
        reason = result.get('reason') or 'part not in target bin'
        if 'not inside' in reason or 'still held' in reason:
            reason = 'part not in target bin'
        return f'Rejected: {reason}'
    if not _positive_number(result.get('time')) or not _positive_number(result.get('steps_done')):
        return 'Rejected: invalid simulation measurements'
    return None


def score(results):
    """Rank simulator results without changing them; reject before normalizing.

    Safe plans receive 60 + 20 * fastest/time + 20 * shortest/steps_done.
    References include safe plans only. Equal scores preserve input order.
    Each row keeps the original result for the pipeline's media/UI handoff.
    """
    rows = []
    for result in results:
        reason = _rejection(result)
        rows.append(dict(plan_id=result.get('plan_id'), score=0.,
                         status='Rejected' if reason else 'OK', reason=reason or '', result=result))
    accepted = [row for row in rows if row['status'] == 'OK']
    if accepted:
        fastest = min(row['result']['time'] for row in accepted)
        shortest = min(row['result']['steps_done'] for row in accepted)
        for row in accepted:
            result = row['result']
            row['score'] = round(60 + 20 * fastest / result['time']
                                 + 20 * shortest / result['steps_done'], 2)
            reasons = []
            if result['time'] > fastest:
                reasons.append(f"{result['time'] - fastest:.2f} s slower than fastest safe plan")
            if result['steps_done'] > shortest:
                reasons.append(f"{result['steps_done'] - shortest:g} more steps than shortest safe plan")
            row['reason'] = 'OK: ' + ('; '.join(reasons) or 'fastest and shortest safe plan')
    return sorted(rows, key=lambda row: (row['status'] != 'OK', -row['score']))
