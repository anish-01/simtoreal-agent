"""Day 3 examples shared by the validation CLI and future UI buttons."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO_TASKS = {
    'easy': dict(task='Put the red part in bin A', goals={'red_part': 'bin_a'},
                 scene=ROOT / 'scenes/factory.xml', plan=ROOT / 'examples/red_to_bin_a.json'),
    'medium': dict(task='Sort both parts by color', goals={'red_part': 'bin_a', 'blue_part': 'bin_b'},
                   scene=ROOT / 'scenes/factory.xml', plan=ROOT / 'examples/sort_by_color.json'),
    'unreachable': dict(task='Put the blue part in bin B', goals={'blue_part': 'bin_b'},
                        scene=ROOT / 'scenes/factory_unreachable.xml', plan=ROOT / 'examples/blue_to_bin_b.json'),
}


def expected_outcome(name, result):
    """Check the full pipeline response, including never selecting an unsafe plan."""
    rows = result['table']
    if not rows or result['goals'] != DEMO_TASKS[name]['goals']:
        return False
    if name == 'unreachable':
        return (result['best'] is None and result['error'] == 'no safe plan found'
                and all(row['status'] == 'Rejected' and row['score'] == 0
                        and 'could not reach' in row['reason'] for row in rows))
    minimum = 2 if name == 'easy' and len(rows) > 1 else 1
    return (not result['error'] and result['best'] is not None
            and result['best']['status'] == 'OK'
            and sum(row['status'] == 'OK' for row in rows) >= minimum)
