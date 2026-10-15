"""Score arithmetic and safety decisions without rendering or a model service."""
from copy import deepcopy
import math
import pytest
from scorer import score


def result(plan_id=1, **changes):
    return dict(dict(plan_id=plan_id, success=True, time=4., steps_done=4,
                     collisions=0, dropped=False, failed_step=None, reason=''), **changes)


def test_weighted_scores_sorted_and_explained_without_mutation():
    results = [result(1, time=8., steps_done=8), result(2), result(3, time=8.)]
    original = deepcopy(results)
    rows = score(results)
    assert [(r['plan_id'], r['score']) for r in rows] == [(2, 100.), (3, 90.), (1, 80.)]
    assert '4.00 s slower' in rows[2]['reason'] and '4 more steps' in rows[2]['reason']
    assert results == original and rows[0]['result'] is results[1]


@pytest.mark.parametrize('changes,reason', [
    ({'collisions': 1}, 'Rejected: arm hit the table'),
    ({'dropped': True}, 'Rejected: dropped part'),
    ({'failed_step': 2, 'reason': 'timeout'}, 'Rejected: step 2 failed (timeout)'),
    ({'success': False, 'reason': 'red_part is not inside bin_a'}, 'Rejected: part not in target bin'),
    ({'success': False, 'reason': 'simulation timed out after 180 s'}, 'Rejected: simulation timed out after 180 s'),
    ({'success': False}, 'Rejected: part not in target bin'),
])
def test_reject_even_when_success_flag_is_inconsistent(changes, reason):
    row = score([result(**changes)])[0]
    assert (row['status'], row['score'], row['reason']) == ('Rejected', 0., reason)


def test_unsafe_fast_short_plan_cannot_change_safe_scores():
    rows = score([result(1, collisions=1, time=.1, steps_done=1), result(2)])
    assert [(r['plan_id'], r['score']) for r in rows] == [(2, 100.), (1, 0.)]


@pytest.mark.parametrize('field', ['time', 'steps_done'])
@pytest.mark.parametrize('value', [0, -1, math.nan, math.inf, True, None])
def test_invalid_measurements_are_not_approved(field, value):
    assert score([result(**{field: value})])[0]['status'] == 'Rejected'


def test_empty_all_rejected_and_ties():
    assert score([]) == []
    assert all(r['score'] == 0 for r in score([result(success=False), result(2, dropped=True)]))
    assert [r['plan_id'] for r in score([result(2), result(1)])] == [2, 1]
