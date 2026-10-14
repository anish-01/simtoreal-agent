"""Offline tests for the planner prompt contract: no LLM server needed."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import planner

RED_TO_A = {'plan_id': 1, 'steps': [
    {'action': 'move_to', 'target': 'red_part'}, {'action': 'grasp'},
    {'action': 'move_to', 'target': 'bin_a'}, {'action': 'release'}]}


def test_plan_format_example_is_valid():
    assert planner.validate(RED_TO_A) == (True, '')


def test_sort_both_with_lift_and_home_is_valid():
    plan = {'steps': [
        {'action': 'move_to', 'target': 'red_part'}, {'action': 'grasp'}, {'action': 'lift', 'height': .1},
        {'action': 'move_to', 'target': 'bin_a'}, {'action': 'release'},
        {'action': 'move_to', 'target': 'blue_part'}, {'action': 'grasp'}, {'action': 'lift'},
        {'action': 'move_to', 'target': 'bin_b'}, {'action': 'release'}, {'action': 'home'}]}
    assert planner.validate(plan)[0]


@pytest.mark.parametrize('plan, reason', [
    ([], 'not a JSON object'),
    ({'steps': []}, 'non-empty'),
    ({'steps': [{'action': 'fly'}]}, 'unknown action'),
    ({'steps': [{'action': 'move_to', 'target': 'bin_c'}]}, 'unknown target'),
    ({'steps': [{'action': 'move_to'}]}, 'unknown target'),
    ({'steps': [{'action': 'grasp'}]}, 'directly follow'),
    ({'steps': [{'action': 'move_to', 'target': 'bin_a'}, {'action': 'grasp'}]}, 'directly follow'),
    ({'steps': [{'action': 'move_to', 'target': 'red_part'}, {'action': 'lift'}, {'action': 'grasp'}]}, 'directly follow'),
    ({'steps': [{'action': 'move_to', 'target': 'red_part'}, {'action': 'grasp'},
                {'action': 'move_to', 'target': 'blue_part'}, {'action': 'grasp'}]}, 'already holding'),
    ({'steps': [{'action': 'lift', 'height': 2}]}, 'lift height'),
    ({'steps': [{'action': 'lift', 'height': True}]}, 'lift height'),
    ({'steps': [{'action': 'grasp', 'target': 'red_part'}]}, 'unexpected fields'),
    ({'steps': [{'action': 'home'}] * 17}, 'too many steps'),
])
def test_invalid_plans_are_rejected(plan, reason):
    ok, why = planner.validate(plan)
    assert not ok and reason in why


def test_parse_tolerates_text_and_fence():
    raw = 'Here is the plan:\n```json\n' + json.dumps(RED_TO_A) + '\n```'
    assert planner.parse(raw) == RED_TO_A


def test_prompt_names_every_action_and_object():
    for word in planner.ACTIONS + planner.TARGETS:
        assert word in planner.SYSTEM_PROMPT


class FakeLLM:
    def __init__(self, reply):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.reply = reply

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])


def test_request_plan_uses_json_mode_and_sets_plan_id():
    llm = FakeLLM(json.dumps({**RED_TO_A, 'plan_id': 99}))
    plan, reason, _ = planner.request_plan('put red part in bin A', plan_id=3, llm=llm)
    assert reason == '' and plan['plan_id'] == 3
    call = llm.calls[0]
    assert call['response_format'] == {'type': 'json_object'}


def test_request_plan_reports_bad_json():
    plan, reason, raw = planner.request_plan('x', llm=FakeLLM('sorry, I cannot'))
    assert plan is None and 'invalid JSON' in reason and raw == 'sorry, I cannot'


def test_temperatures_spread_from_low_to_high():
    assert planner.temperatures(8) == [.2, .314, .429, .543, .657, .771, .886, 1.]
    assert planner.temperatures(1) == [.2]


class ScriptedLLM(FakeLLM):
    """Candidate 3 always replies with broken JSON; candidate 5 fails once, then succeeds."""
    def __init__(self):
        super().__init__(None)
        self.failed_once = False

    def create(self, **kwargs):
        self.calls.append(kwargs)
        task = kwargs['messages'][1]['content']
        if 'plan 3 of' in task:
            reply = 'not json'
        elif 'plan 5 of' in task and not self.failed_once:
            self.failed_once, reply = True, '{"steps": [{"action": "fly"}]}'
        else:
            reply = json.dumps(RED_TO_A)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])


def test_generate_plans_retries_then_drops_bad_candidates():
    llm = ScriptedLLM()
    plans = planner.generate_plans('put red part in bin A', n=8, llm=llm)
    assert [p['plan_id'] for p in plans] == [1, 2, 4, 5, 6, 7, 8]
    assert len(llm.calls) == 8 + planner.RETRIES + 1
    assert sorted({c['temperature'] for c in llm.calls}) == planner.temperatures(8)


def test_generate_plans_survives_request_errors():
    class DownLLM(FakeLLM):
        def create(self, **kwargs):
            raise ConnectionError('server down')
    assert planner.generate_plans('x', n=2, llm=DownLLM(None)) == []


def test_run_folders_are_unique_and_hold_task_and_plans(tmp_path):
    import runlog
    first, second = runlog.new_run('put red part in bin A', tmp_path), runlog.new_run('again', tmp_path)
    assert first != second and (first / 'task.txt').read_text() == 'put red part in bin A\n'
    path = runlog.save_json(first, 'plans.json', [RED_TO_A])
    assert json.loads(path.read_text()) == [RED_TO_A]

def test_each_candidate_gets_a_different_style():
    llm = FakeLLM(json.dumps(RED_TO_A))
    planner.generate_plans('put red part in bin A', n=8, llm=llm)
    messages = {c['messages'][1]['content'] for c in llm.calls}
    assert len(messages) == 8
    assert all('Style:' in m for m in messages)
