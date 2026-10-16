"""Pipeline tests: real parallel MuJoCo runs with a fake LLM, so no model server is needed."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planner
import pipeline

RED_TO_A = json.loads((Path(__file__).resolve().parents[1] / 'examples' / 'red_to_bin_a.json').read_text())
WRONG_BIN = {'plan_id': 2, 'steps': [
    {'action': 'move_to', 'target': 'red_part'}, {'action': 'grasp'},
    {'action': 'move_to', 'target': 'bin_b'}, {'action': 'release'}]}


class TaskLLM:
    """Answers the goals prompt with `goals` and every plan request with the next plan in `plans`."""
    def __init__(self, goals, plans):
        self.goals, self.plans = goals, plans
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        system, user = kwargs['messages'][0]['content'], kwargs['messages'][1]['content']
        if system == planner.GOALS_PROMPT:
            reply = json.dumps({'goals': self.goals})
        else:
            k = int(user.rsplit('Candidate plan ', 1)[1].split(' ')[0])
            reply = json.dumps(self.plans[(k - 1) % len(self.plans)])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])


def test_extract_goals_validates_parts_and_bins():
    assert planner.extract_goals('x', TaskLLM({'red_part': 'bin_a'}, [])) == ({'red_part': 'bin_a'}, '')
    assert planner.extract_goals('x', TaskLLM({'red_part': 'bin_c'}, []))[0] is None
    assert planner.extract_goals('x', TaskLLM({}, []))[0] is None


def test_run_all_parallel_matches_sequential(tmp_path):
    goals = {'red_part': 'bin_a'}
    plans = [RED_TO_A, WRONG_BIN]
    seq = pipeline.run_all(plans, goals, tmp_path / 'seq', parallel=False)
    par = pipeline.run_all(plans, goals, tmp_path / 'par', parallel=True)
    assert [r['success'] for r in seq] == [r['success'] for r in par] == [True, False]
    assert all(Path(r['video_path']).exists() for r in par)


def test_run_all_reports_timeouts_instead_of_hanging(tmp_path):
    results = pipeline.run_all([RED_TO_A], {'red_part': 'bin_a'}, tmp_path, timeout=.01)
    assert results[0]['success'] is False and 'timed out' in results[0]['reason']


def test_run_task_ranks_plans_and_saves_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.verifier, 'verify', lambda image, goals, success: dict(answer='yes', needs_review=False, seconds=.5))
    steps = []
    result = pipeline.run_task('Put the red part in bin A', n=2, llm=TaskLLM({'red_part': 'bin_a'}, [RED_TO_A, WRONG_BIN]),
                               progress=lambda f, m: steps.append(m), root=tmp_path)
    assert result['error'] == '' and result['goals'] == {'red_part': 'bin_a'}
    assert [row['status'] for row in result['table']] == ['OK', 'Rejected']
    assert result['best']['plan_id'] == 1 and steps[-1] == 'Done'
    assert set(result['timings']) == {'llm_s', 'sim_s', 'vision_s', 'total_s'}
    assert result['best']['vision']['needs_review'] is False
    saved = Path(result['run_dir'])
    assert {'task.txt', 'goals.json', 'plans.json', 'results.json'} <= {p.name for p in saved.iterdir()}


def test_run_task_stops_on_unclear_task(tmp_path):
    result = pipeline.run_task('Make me a sandwich', llm=TaskLLM({}, []), root=tmp_path)
    assert result['best'] is None and 'does not ask' in result['error'] and result['plans'] == []
